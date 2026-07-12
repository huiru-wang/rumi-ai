"""Style extraction manager: parse PPTX -> per-slide understanding -> style -> preview."""

import asyncio
import json
import logging
import os
import re
from pathlib import Path

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI

from src.exceptions import BusinessError, BusinessErrorCode
from src.managers.prompt_manager import PromptManager
from src.managers.style_extract_utils import (
    PAGE_TYPES,
    parse_frontmatter,
    resolve_style_name_en,
    validate_preview_html,
    validate_style_description,
)
from src.managers.style_llm_runner import StyleLLMRunner
from src.parsers.pptx_parser import parse_pptx_to_structured, write_parse_outputs
from src.storage.database import Database
from src.storage.file_store import FileStore
from src.storage.workspace_paths import reset_dir, style_extract_dir
from src.url_utils import build_style_extraction_resource_url, build_style_resource_url

logger = logging.getLogger(__name__)

_EXCLUDED_PAGE_TEXT = re.compile(r"授权|版权|来源|素材|下载|水印|license|copyright|source", re.I)


def _target_filename(target: str) -> str:
    return Path(target.replace("\\", "/")).name


def build_background_manifest(parsed: dict, available_files: set[str] | None = None) -> list[dict]:
    """Build a background-only manifest from structured slide data."""
    page_size = parsed.get("deck_meta", {}).get("page_size", {})
    page_width = float(page_size.get("width") or 0)
    page_height = float(page_size.get("height") or 0)
    resources: dict[str, set[int]] = {}

    for slide in parsed.get("slides", []):
        slide_no = int(slide.get("slide_no") or 0)
        text = " ".join(
            str(shape.get("text", {}).get("fullText", ""))
            for shape in slide.get("shapes", [])
        )
        if _EXCLUDED_PAGE_TEXT.search(text):
            continue

        filenames: set[str] = set()
        background = slide.get("background") or {}
        if background.get("type") == "image" and background.get("target"):
            filenames.add(_target_filename(background["target"]))

        for shape in slide.get("shapes", []):
            fill = shape.get("fill") or {}
            if shape.get("kind") != "pic" or fill.get("type") != "image" or not fill.get("target"):
                continue
            if not page_width or not page_height:
                continue
            width = float(shape.get("width") or 0)
            height = float(shape.get("height") or 0)
            x = float(shape.get("x") or 0)
            y = float(shape.get("y") or 0)
            if width >= page_width * 0.9 and height >= page_height * 0.9 and x <= page_width * 0.05 and y <= page_height * 0.05:
                filenames.add(_target_filename(fill["target"]))

        for filename in filenames:
            if available_files is None or filename in available_files:
                resources.setdefault(filename, set()).add(slide_no)

    return [
        {
            "filename": filename,
            "slides": sorted(slides),
            "usage_type": "background",
        }
        for filename, slides in sorted(resources.items())
    ]


def _fallback_understanding(slide: dict, error: Exception) -> dict:
    slide_no = int(slide.get("slide_no") or 0)
    return {
        "slide_no": slide_no,
        "page_type": "cover" if slide_no == 1 else "content",
        "page_type_confidence": 0,
        "layout_family": "parser_fallback",
        "visual_role": "other",
        "composition": {"structure": "由结构化解析结果降级生成", "density": "medium", "hierarchy": [], "safe_zones": ""},
        "color_usage": {"background": [], "surface": [], "text": [], "accent": [], "notes": ""},
        "typography_usage": {"title_style": "", "body_style": "", "notes": ""},
        "assets": [],
        "signature_elements": [],
        "merge_hints": [],
        "quality_notes": [f"单页理解失败：{type(error).__name__}"],
    }


class StyleExtractManager:
    """Manage the complete asynchronous PPTX style extraction workflow."""

    def __init__(
        self,
        db: Database,
        file_store: FileStore,
        llm_runner: StyleLLMRunner | None = None,
        prompt_manager: PromptManager | None = None,
    ):
        self.db = db
        self.file_store = file_store
        self._prompt_manager = prompt_manager or PromptManager()
        self._llm_runner = llm_runner or StyleLLMRunner()
        self._active_tasks: dict[str, asyncio.Event] = {}
        vision_model = os.getenv("VISION_MODEL")
        self._vision_llm = ChatOpenAI(
            model=vision_model,
            api_key=os.getenv("VISION_API_KEY"),
            base_url=os.getenv("VISION_API_BASE"),
        ) if vision_model else None

    async def run_extraction(self, task_id: str, workspace_id: str, pptx_content: bytes, pptx_filename: str):
        cancel_event = asyncio.Event()
        self._active_tasks[task_id] = cancel_event
        warnings: list[str] = []
        try:
            await self._check_cancel(cancel_event)
            await self._update_progress(task_id, "parsing", pptx_filename=pptx_filename)

            user_id = await self.file_store._resolve_user_id(workspace_id)
            ws_prefix = self.file_store._ws_prefix(user_id, workspace_id)
            resource_prefix = f"{ws_prefix}/style/{task_id}"
            pptx_key = f"{resource_prefix}/source.pptx"
            await self.file_store._provider.save_async(pptx_key, pptx_content)

            work_dir = reset_dir(style_extract_dir(workspace_id, task_id))
            source_dir = work_dir / "source"
            source_dir.mkdir(parents=True, exist_ok=True)
            source_pptx = source_dir / "source.pptx"
            source_pptx.write_bytes(pptx_content)

            parsed = await asyncio.to_thread(
                parse_pptx_to_structured,
                str(source_pptx),
                str(work_dir),
                str(work_dir / "pptx_unpack"),
            )
            _, parsed_json, parsed_md = write_parse_outputs(parsed, str(work_dir))

            resource_dir = work_dir / "resource"
            available_files = {path.name for path in resource_dir.iterdir() if path.is_file()} if resource_dir.exists() else set()
            for filename in sorted(available_files):
                await self.file_store._provider.save_async(
                    f"{resource_prefix}/resource/{filename}",
                    (resource_dir / filename).read_bytes(),
                )

            resource_manifest = []
            for resource in build_background_manifest(parsed, available_files):
                filename = resource["filename"]
                analysis = None
                if self._vision_llm:
                    signed_url = self.file_store._provider.get_url(f"{resource_prefix}/resource/{filename}")
                    analysis = await self._analyze_image_resource(signed_url, filename)
                resource_manifest.append({
                    "filename": filename,
                    "url": build_style_extraction_resource_url(task_id, filename),
                    "used_in_slides": resource["slides"],
                    "usage_type": "background",
                    "description": analysis or {},
                })

            work_files = {
                "parsed_json": str(parsed_json),
                "parsed_md": str(parsed_md),
                "slide_understandings": str(work_dir / "slide_understandings.json"),
                "style_template": str(work_dir / "style_template.md"),
            }
            await self._update_progress(
                task_id,
                "analyzing_style",
                pptx_filename=pptx_filename,
                pptx_storage_key=pptx_key,
                resource_prefix=resource_prefix,
                resource_manifest=resource_manifest,
                work_files=work_files,
                warnings=warnings,
            )

            understandings = await self._understand_slides_sequentially(
                task_id, parsed, resource_manifest, work_dir, cancel_event, warnings
            )
            raw_style_output = await self._merge_style_template(parsed, understandings, resource_manifest)
            parsed_style = parse_frontmatter(raw_style_output)
            style_name = parsed_style["name"] or "未命名风格"
            style_name_en = resolve_style_name_en(parsed_style["name_en"], style_name)
            description = parsed_style["description"]
            style_description = parsed_style["style_description"]

            style_errors = validate_style_description(style_description, style_name, description)
            if style_errors:
                warnings.extend(f"风格模板校验：{error}" for error in style_errors)
                raw_style_output = await self._repair_style(raw_style_output, style_errors, understandings, resource_manifest)
                parsed_style = parse_frontmatter(raw_style_output)
                style_name = parsed_style["name"] or style_name
                style_name_en = resolve_style_name_en(parsed_style["name_en"], style_name)
                description = parsed_style["description"] or description
                style_description = parsed_style["style_description"]
                remaining = validate_style_description(style_description, style_name, description)
                if remaining:
                    raise BusinessError(
                        BusinessErrorCode.STYLE_EXTRACTION_TEMPLATE_INVALID,
                        stage="style_template_repair",
                    )

            (work_dir / "style_template.md").write_text(raw_style_output, encoding="utf-8")
            await self._check_cancel(cancel_event)
            await self._update_progress(
                task_id,
                "generating_preview",
                description=description,
                style_description=style_description,
                style_name=style_name,
                style_name_en=style_name_en,
                warnings=warnings,
            )

            preview_html = await self._generate_preview_html(style_description, resource_manifest)
            preview_errors = validate_preview_html(preview_html, style_description)
            if preview_errors:
                warnings.extend(f"预览校验：{error}" for error in preview_errors)
                preview_html = await self._repair_preview(preview_html, preview_errors, style_description, resource_manifest)
                remaining = validate_preview_html(preview_html, style_description)
                if remaining:
                    raise BusinessError(
                        BusinessErrorCode.STYLE_EXTRACTION_PREVIEW_INVALID,
                        stage="preview_repair",
                    )

            (work_dir / "preview.html").write_text(preview_html, encoding="utf-8")
            preview_path = await self.file_store.save_style_output(
                workspace_id, task_id, "preview.html", preview_html.encode("utf-8")
            )
            result_data = {
                "description": description,
                "style_description": style_description,
                "style_name": style_name,
                "style_name_en": style_name_en,
                "preview_html_path": preview_path,
                "pptx_filename": pptx_filename,
                "pptx_storage_key": pptx_key,
                "resource_prefix": resource_prefix,
                "resource_manifest": resource_manifest,
                "work_files": work_files,
                "warnings": warnings,
                "progress_step": "completed",
            }
            await self.db.update_task(
                task_id,
                status="completed",
                title=style_name,
                result_data=json.dumps(result_data, ensure_ascii=False),
            )
        except _CancelledError:
            await self.db.update_task(task_id, status="cancelled")
        except Exception as exc:
            logger.error("[StyleExtract] task=%s failed: %s", task_id, exc, exc_info=True)
            error = exc if isinstance(exc, BusinessError) else BusinessError(
                BusinessErrorCode.STYLE_EXTRACTION_UNKNOWN
            )
            error_data = await self.db.get_task_result_data(task_id)
            error_data.update({
                "error": error.to_dict(),
                "pptx_filename": pptx_filename,
                "warnings": warnings,
                "progress_step": "failed",
            })
            await self.db.update_task(
                task_id,
                status="failed",
                result_data=json.dumps(error_data, ensure_ascii=False),
            )
        finally:
            self._active_tasks.pop(task_id, None)

    async def _understand_slides_sequentially(
        self,
        task_id: str,
        parsed: dict,
        resource_manifest: list[dict],
        work_dir: Path,
        cancel_event: asyncio.Event,
        warnings: list[str],
    ) -> list[dict]:
        understandings: list[dict] = []
        slides = parsed.get("slides", [])
        deck_context = {
            "deck_meta": parsed.get("deck_meta", {}),
            "theme": parsed.get("theme", {}),
            "warnings": parsed.get("warnings", []),
        }
        for index, slide in enumerate(slides):
            await self._check_cancel(cancel_event)
            slide_no = int(slide.get("slide_no") or index + 1)
            user_prompt = (
                f"请分析第 {slide_no} 页并输出 JSON。\n\n"
                f"deck_context:\n{json.dumps(deck_context, ensure_ascii=False)}\n\n"
                f"slide_data:\n{json.dumps(slide, ensure_ascii=False)}\n\n"
                f"resource_manifest:\n{json.dumps(resource_manifest, ensure_ascii=False)}\n\n"
                f"previous_page_type_hint:\n{understandings[-1].get('page_type', '') if understandings else ''}"
            )
            try:
                result = await self._llm_runner.invoke_json(
                    system_prompt=self._prompt_manager.get_style_slide_understanding_prompt(),
                    user_prompt=user_prompt,
                    purpose=f"style_slide_understanding:{slide_no}",
                )
                result["slide_no"] = slide_no
                if result.get("page_type") not in (*PAGE_TYPES, "exclude"):
                    raise BusinessError(
                        BusinessErrorCode.STYLE_EXTRACTION_OUTPUT_INVALID,
                        stage=f"slide_understanding:{slide_no}",
                    )
            except BusinessError as exc:
                if exc.error in {
                    BusinessErrorCode.STYLE_EXTRACTION_MODEL_AUTH,
                    BusinessErrorCode.STYLE_EXTRACTION_MODEL_QUOTA,
                    BusinessErrorCode.STYLE_EXTRACTION_MODEL_RATE_LIMIT,
                    BusinessErrorCode.STYLE_EXTRACTION_MODEL_TIMEOUT,
                    BusinessErrorCode.STYLE_EXTRACTION_MODEL_CONNECTION,
                }:
                    raise
                logger.warning("[StyleExtract] slide %s fallback: code=%s", slide_no, exc.code)
                warnings.append(f"第 {slide_no} 页理解失败，已使用结构化降级结果")
                result = _fallback_understanding(slide, exc)
            except Exception as exc:
                logger.warning("[StyleExtract] slide %s fallback: %s", slide_no, exc)
                warnings.append(f"第 {slide_no} 页理解失败，已使用结构化降级结果")
                result = _fallback_understanding(slide, exc)
            understandings.append(result)
            (work_dir / "slide_understandings.json").write_text(
                json.dumps(understandings, ensure_ascii=False, indent=2), encoding="utf-8"
            )
            await self._update_progress(
                task_id,
                "analyzing_style",
                current_slide=slide_no,
                total_slides=len(slides),
                warnings=warnings,
            )
        return understandings

    async def _merge_style_template(self, parsed: dict, understandings: list[dict], resource_manifest: list[dict]) -> str:
        included = [item for item in understandings if item.get("page_type") != "exclude"]
        user_prompt = (
            "请生成完整 PPT 风格模板。\n\n"
            f"deck_summary:\n{json.dumps({'deck_meta': parsed.get('deck_meta'), 'theme': parsed.get('theme')}, ensure_ascii=False)}\n\n"
            f"slide_understandings:\n{json.dumps(included, ensure_ascii=False)}\n\n"
            f"resource_manifest:\n{json.dumps(resource_manifest, ensure_ascii=False)}\n\n"
            f"parser_notes:\n{json.dumps(parsed.get('warnings', []), ensure_ascii=False)}"
        )
        return await self._llm_runner.invoke_text(
            system_prompt=self._prompt_manager.get_style_merge_prompt(),
            user_prompt=user_prompt,
            purpose="style_merge_template",
        )

    async def _repair_style(self, original: str, errors: list[str], understandings: list[dict], resource_manifest: list[dict]) -> str:
        return await self._llm_runner.invoke_text(
            system_prompt=self._prompt_manager.get_style_merge_prompt(),
            user_prompt=(
                "修复以下风格模板，只输出修复后的完整 Markdown。正文允许 fenced code block。\n"
                f"校验错误：{json.dumps(errors, ensure_ascii=False)}\n"
                f"逐页理解：{json.dumps(understandings, ensure_ascii=False)}\n"
                f"背景资源：{json.dumps(resource_manifest, ensure_ascii=False)}\n"
                f"原模板：\n{original}"
            ),
            purpose="style_merge_repair",
        )

    async def _generate_preview_html(self, style_description: str, resource_manifest: list[dict]) -> str:
        return await self._llm_runner.invoke_html(
            system_prompt=self._prompt_manager.build_style_preview_prompt(style_description, "", resource_manifest),
            user_prompt="生成完整只读预览 HTML，覆盖全部启用页面类型和关键布局变体。",
            purpose="style_preview_html",
        )

    async def _repair_preview(self, original: str, errors: list[str], style_description: str, resource_manifest: list[dict]) -> str:
        return await self._llm_runner.invoke_html(
            system_prompt=self._prompt_manager.build_style_preview_prompt(style_description, "", resource_manifest),
            user_prompt=(
                "修复以下 HTML，只输出完整 HTML。\n"
                f"校验错误：{json.dumps(errors, ensure_ascii=False)}\n"
                f"原 HTML：\n{original}"
            ),
            purpose="style_preview_repair",
        )
    async def cancel_extraction(self, task_id: str):
        """中断正在执行的工作流。"""
        event = self._active_tasks.get(task_id)
        if event:
            event.set()
            logger.info("[StyleExtract] cancel requested for task=%s", task_id)

    async def save_as_custom_style(self, task_id: str, user_id: str) -> dict:
        """将已完成任务的产出保存为自定义风格到 ppt_style 表。

        Migrates all files (source PPTX, resource images, preview HTML)
        from the workspace task directory to the user style directory.
        """
        await self.db.ensure_initialized()
        task = await self.db.get_task(task_id)
        if not task:
            raise BusinessError(BusinessErrorCode.TASK_NOT_FOUND)
        if task["status"] != "completed":
            raise BusinessError(BusinessErrorCode.TASK_NOT_COMPLETED)

        result_data = task.get("result_data")
        if isinstance(result_data, str):
            result_data = json.loads(result_data)
        if not result_data:
            raise BusinessError(BusinessErrorCode.TASK_NOT_COMPLETED)

        # Duplicate save check
        if result_data.get("saved_style_id"):
            raise BusinessError(BusinessErrorCode.STYLE_ALREADY_SAVED)

        style_name = result_data.get("style_name", "未命名风格")
        style_name_en = result_data.get("style_name_en", "unnamed-style")
        style_description = result_data.get("style_description", "")
        description = result_data.get("description", "")

        # Create style record in DB
        style = await self.db.create_ppt_style(
            user_id=user_id,
            category="custom",
            name=style_name,
            name_en=style_name_en,
            description=description,
            style_description=style_description,
            preview_path="",  # Will be updated after migration
        )

        style_id = style["id"]

        # Migrate all resources from task directory to user style directory
        resource_prefix = result_data.get("resource_prefix", "")
        pptx_storage_key = result_data.get("pptx_storage_key", "")
        preview_html_path = result_data.get("preview_html_path", "")

        target_prefix = f"user/{user_id}/style/{style_id}"
        migrated_preview_path = ""

        try:
            # 1. Migrate source PPTX
            if pptx_storage_key:
                pptx_filename = result_data.get("pptx_filename", "source.pptx")
                content = await self.file_store.read(pptx_storage_key)
                dest_key = f"{target_prefix}/{pptx_filename}"
                await self.file_store._provider.save_async(dest_key, content)
                logger.info("[StyleExtract] migrated PPTX to: %s", dest_key)

            # 2. Migrate resource images (resource/ subdirectory)
            if resource_prefix:
                src_resource_prefix = f"{resource_prefix}/resource/"
                # For OSS: list objects with prefix and copy
                # For local: copy directory contents
                if not self.file_store._provider.is_local:
                    # OSS: iterate and copy
                    import oss2  # type: ignore
                    provider = self.file_store._provider
                    for obj in oss2.ObjectIterator(provider._bucket, prefix=src_resource_prefix):
                        if obj.key.endswith("/"):
                            continue  # Skip directory markers
                        filename = obj.key.split("/")[-1]
                        content = await self.file_store.read(obj.key)
                        dest_key = f"{target_prefix}/resource/{filename}"
                        await self.file_store._provider.save_async(dest_key, content)
                        logger.debug("[StyleExtract] migrated resource: %s -> %s", obj.key, dest_key)
                else:
                    # Local: copy directory
                    src_dir = self.file_store.base_dir / src_resource_prefix.rstrip("/")
                    if src_dir.exists() and src_dir.is_dir():
                        for img_file in sorted(src_dir.iterdir()):
                            if img_file.is_file():
                                content = img_file.read_bytes()
                                dest_key = f"{target_prefix}/resource/{img_file.name}"
                                await self.file_store._provider.save_async(dest_key, content)
                                logger.debug("[StyleExtract] migrated resource: %s", dest_key)

            # 3. Migrate preview HTML
            if preview_html_path:
                if await self.file_store.exists(preview_html_path):
                    content = await self.file_store.read(preview_html_path)
                    dest_key = f"{target_prefix}/preview.html"
                    new_preview_path = await self.file_store._provider.save_async(dest_key, content)
                    await self.db.update_ppt_style_preview_path(style_id, new_preview_path)
                    style["preview_path"] = new_preview_path
                    migrated_preview_path = new_preview_path
                    logger.info("[StyleExtract] migrated preview HTML to: %s", new_preview_path)

        except Exception as e:
            logger.error("[StyleExtract] file migration failed for style %s: %s", style_id, e, exc_info=True)
            # Don't fail the save - DB record is already created

        # Update resource manifest URLs and style_description after migration
        resource_manifest = result_data.get("resource_manifest", [])
        if resource_manifest and resource_prefix:
            # Frontend-facing resources must go through the API proxy; never
            # persist OSS public URLs or object keys into style metadata.

            url_replacements: list[tuple[str, str]] = []
            for res in resource_manifest:
                old_url = res.get("url", "")
                if old_url:
                    filename = res.get("filename", "")
                    new_url = build_style_resource_url(style_id, filename) if filename else ""
                    url_replacements.append((old_url, new_url))
                    res["url"] = new_url

            # Update style_description with new URLs
            if url_replacements:
                updated_desc = style_description
                for old_url, new_url in url_replacements:
                    updated_desc = updated_desc.replace(old_url, new_url)
                if updated_desc != style_description:
                    style_description = updated_desc
                    logger.info("[StyleExtract] updated %d resource URLs in style %s", len(url_replacements), style_id)
                if migrated_preview_path and await self.file_store.exists(migrated_preview_path):
                    preview_html = await self.file_store.read_text(migrated_preview_path)
                    updated_html = preview_html
                    for old_url, new_url in url_replacements:
                        updated_html = updated_html.replace(old_url, new_url)
                    if updated_html != preview_html:
                        await self.file_store.write_text(migrated_preview_path, updated_html)
                        logger.info("[StyleExtract] updated resource URLs in preview HTML for style %s", style_id)

        # Persist resource_manifest and updated style_description to ppt_style
        update_fields: dict = {
            "resource_manifest": json.dumps(resource_manifest, ensure_ascii=False),
        }
        if style_description != result_data.get("style_description", ""):
            update_fields["style_description"] = style_description
        await self.db.update_ppt_style(style_id, **update_fields)
        logger.info("[StyleExtract] persisted resource_manifest (%d items) to style %s", len(resource_manifest), style_id)

        # Mark task as saved to prevent duplicate saves
        result_data["saved_style_id"] = style_id
        await self.db.update_task(
            task_id,
            result_data=json.dumps(result_data, ensure_ascii=False),
        )

        logger.info("[StyleExtract] saved custom style: id=%s name=%s user=%s", style_id, style_name, user_id)
        return style

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    async def _analyze_image_resource(self, image_url: str, filename: str) -> dict | None:
        """使用视觉模型分析单张背景图片，返回结构化描述。

        Args:
            image_url: 图片的公开 HTTP URL
            filename: 图片文件名（用于日志）

        Returns:
            结构化描述 dict，失败时返回 None
        """
        if not self._vision_llm:
            return None
        if not image_url.startswith(("http://", "https://")):
            logger.debug("[StyleExtract] skipping vision analysis: non-public URL for %s", filename)
            return None
        try:
            messages = [
                SystemMessage(content=(
                    "你是 PPT 背景图片分析专家。分析给定的 PPT 背景图片，输出 JSON 格式的结构化描述。\n"
                    "输出字段：style, visual_theme, color_tone, composition, safe_zones, usage_notes。\n"
                    "每个字段用简洁的中文描述，不超过 30 字。仅输出 JSON，不要其他内容。"
                )),
                HumanMessage(content=[
                    {"type": "text", "text": f"分析这张 PPT 背景图片：{filename}"},
                    {"type": "image_url", "image_url": {"url": image_url}},
                ]),
            ]
            response: AIMessage = await self._vision_llm.ainvoke(messages)
            raw = response.content.strip()
            # 尝试提取 JSON
            json_match = re.search(r"\{[\s\S]*\}", raw)
            if json_match:
                result = json.loads(json_match.group())
                return {
                    "style": result.get("style", ""),
                    "visual_theme": result.get("visual_theme", ""),
                    "color_tone": result.get("color_tone", ""),
                    "composition": result.get("composition", ""),
                    "safe_zones": result.get("safe_zones", ""),
                    "usage_notes": result.get("usage_notes", ""),
                }
            return None
        except Exception as e:
            logger.warning("[StyleExtract] vision analysis failed for %s: %s", filename, e)
            return None

    async def _update_progress(self, task_id: str, step: str, **extra):
        """更新 task 的 status 和 result_data 中的 progress_step。"""
        existing = await self.db.get_task_result_data(task_id)
        existing["progress_step"] = step
        existing.update(extra)
        await self.db.update_task(
            task_id,
            status="generating",
            result_data=json.dumps(existing, ensure_ascii=False),
        )

    async def _check_cancel(self, event: asyncio.Event):
        if event.is_set():
            raise _CancelledError()


class _CancelledError(Exception):
    """内部取消信号。"""
    pass
