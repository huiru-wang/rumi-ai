"""Style extraction manager: parse PPTX -> LLM style template -> LLM preview HTML."""

import asyncio
import json
import logging
import os
import re
import tempfile
from pathlib import Path

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI

from src.agent.style_extract_graph import create_style_extract_graph, resolve_style_name_en
from src.managers.prompt_manager import PromptManager
from src.storage.database import Database
from src.storage.file_store import FileStore
from src.url_utils import build_style_extraction_resource_url, build_style_resource_url

logger = logging.getLogger(__name__)

from src.parsers.pptx_parser import parse_pptx_to_markdown as _parse_pptx_to_markdown


# ============================================================
# Resource Analysis Helpers
# ============================================================
def _extract_visual_resources(markdown_text: str, media_files: dict[str, str] | None = None) -> list[dict]:
    """Extract background image filenames and their slide usage from Markdown.

    Parses patterns like:
        ## 第 1 页
        ### 背景
        背景图片： `../media/Slide-1-image-1.png`

    Ordinary picture/icon resources are intentionally ignored at this stage.
    Returns list of {"filename": "image.png", "slides": [1], "usage_type": "background"}.
    """
    current_slide = None
    resource_map: dict[str, dict] = {}

    def record(filename: str):
        if not filename:
            return
        item = resource_map.setdefault(
            filename,
            {"filename": filename, "slides": set(), "usage_types": {"background"}},
        )
        if current_slide is not None:
            item["slides"].add(current_slide)

    for line in markdown_text.split("\n"):
        line_stripped = line.strip()
        slide_match = re.match(r"## 第 (\d+) 页", line_stripped)
        if slide_match:
            current_slide = int(slide_match.group(1))
            continue

        bg_match = re.search(r"背景图片[：:]\s*`([^`]+)`", line_stripped)
        if bg_match and current_slide is not None:
            path = bg_match.group(1)
            record(path.split("/")[-1])

    resources = []
    for filename in sorted(resource_map):
        item = resource_map[filename]
        usage_types = sorted(item["usage_types"])
        resources.append({
            "filename": filename,
            "slides": sorted(item["slides"]),
            "usage_type": "background",
            "usage_types": usage_types,
        })
    return resources


def _build_resource_section(resource_manifest: list[dict]) -> str:
    """Build a Markdown resource description section to append to the PPTX report."""
    lines = [
        "## 资源描述",
        "",
        "以下是从 PPTX 中提取的视觉资源及其视觉分析。生成风格模板时，必须判断哪些资源应进入风格模板或预览 HTML。",
        "",
    ]

    for res in resource_manifest:
        filename = res["filename"]
        url = res["url"]
        slides = res.get("used_in_slides", [])
        desc = res.get("description", {})

        lines.append(f"### {filename}")
        lines.append(f"- **URL**：`{url}`")
        if slides:
            slide_str = ", ".join(str(s) for s in slides)
            lines.append(f"- **使用页面**：第 {slide_str} 页")
        if res.get("usage_type"):
            lines.append(f"- **资源类型**：{res['usage_type']}")
        if desc.get("style"):
            lines.append(f"- **风格**：{desc['style']}")
        if desc.get("visual_theme"):
            lines.append(f"- **视觉主题**：{desc['visual_theme']}")
        if desc.get("color_tone"):
            lines.append(f"- **色调**：{desc['color_tone']}")
        if desc.get("composition"):
            lines.append(f"- **构图**：{desc['composition']}")
        if desc.get("safe_zones"):
            lines.append(f"- **安全区**：{desc['safe_zones']}")
        if desc.get("usage_notes"):
            lines.append(f"- **使用建议**：{desc['usage_notes']}")
        lines.append("")

    return "\n".join(lines)


class StyleExtractManager:
    """管理 PPTX 风格提取的完整异步工作流。"""

    def __init__(self, db: Database, file_store: FileStore):
        self.db = db
        self.file_store = file_store
        self._prompt_manager = PromptManager()
        self._active_tasks: dict[str, asyncio.Event] = {}
        # 纯文本 LLM: 用于 style_description 和 preview_html 生成
        self._text_llm = ChatOpenAI(
            model=os.getenv("SUMMARIZATION_MODEL"),
            api_key=os.getenv("SUMMARIZATION_API_KEY"),
            base_url=os.getenv("SUMMARIZATION_API_BASE"),
        )
        # 视觉 LLM: 用于背景图片分析（仅在公开 URL 可用时启用）
        _vision_model = os.getenv("VISION_MODEL")
        if _vision_model:
            self._vision_llm = ChatOpenAI(
                model=_vision_model,
                api_key=os.getenv("VISION_API_KEY"),
                base_url=os.getenv("VISION_API_BASE"),
            )
        else:
            self._vision_llm = None

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def run_extraction(self, task_id: str, workspace_id: str, pptx_content: bytes, pptx_filename: str):
        """异步执行完整风格提取工作流。

        Steps:
        1. parsing — 保存源 PPTX + 解析为 Markdown + 提取图片资源
        2. analyzing_style — LLM 生成风格模板（Markdown + frontmatter）
        3. generating_preview — LLM 生成预览 HTML
        4. completed — 保存产出文件
        """
        cancel_event = asyncio.Event()
        self._active_tasks[task_id] = cancel_event

        try:
            # --- Step 1: Save source PPTX + Parse + Extract images ---
            await self._check_cancel(cancel_event)
            await self._update_progress(task_id, "parsing", pptx_filename=pptx_filename)

            # Resolve user_id for path construction
            user_id = await self.file_store._resolve_user_id(workspace_id)
            ws_prefix = self.file_store._ws_prefix(user_id, workspace_id)

            # Save source PPTX to: user/{user_id}/workspace/{workspace_id}/style/{task_id}/{pptx_filename}
            pptx_key = f"{ws_prefix}/style/{task_id}/{pptx_filename}"
            await self.file_store._provider.save_async(pptx_key, pptx_content)
            logger.info("[StyleExtract] saved source PPTX: %s", pptx_key)

            # Determine resource base URL for image paths in Markdown
            resource_prefix = f"{ws_prefix}/style/{task_id}"
            if self.file_store._provider.is_local:
                # Local mode: use the served file URL pattern
                resource_base_url = ""  # Keep original relative paths
            else:
                # OSS mode: use public URL for the resource directory
                resource_base_url = self.file_store._provider.get_public_url(resource_prefix)

            # Parse PPTX to Markdown, extracting images to temp resource dir
            with tempfile.TemporaryDirectory(prefix="style_extract_") as tmp_dir:
                tmp_pptx = Path(tmp_dir) / pptx_filename
                tmp_pptx.write_bytes(pptx_content)

                markdown_text, media_files = await asyncio.to_thread(
                    _parse_pptx_to_markdown,
                    str(tmp_pptx),
                    tmp_dir,
                    resource_base_url,
                )

                # Upload extracted images to FileStore: style/{task_id}/resource/{filename}
                resource_dir = Path(tmp_dir) / "resource"
                if resource_dir.exists():
                    for img_file in sorted(resource_dir.iterdir()):
                        if img_file.is_file():
                            img_key = f"{resource_prefix}/resource/{img_file.name}"
                            img_content = img_file.read_bytes()
                            await self.file_store._provider.save_async(img_key, img_content)
                            logger.debug("[StyleExtract] uploaded resource: %s", img_key)

            logger.info(f"[StyleExtract] PARSED task={task_id} ppt_markdown={markdown_text} media_files={media_files}")

            # --- Step 1.5: Build background resource manifest ---
            resource_manifest: list[dict] = []
            visual_resources = _extract_visual_resources(markdown_text, media_files)
            if visual_resources:
                logger.info("[StyleExtract] background resources found: %d", len(visual_resources))
                for res in visual_resources:
                    filename = res["filename"]
                    img_url = build_style_extraction_resource_url(task_id, filename)
                    analysis = None
                    if self._vision_llm:
                        img_key = f"{resource_prefix}/resource/{filename}"
                        signed_url = self.file_store._provider.get_url(img_key)
                        analysis = await self._analyze_image_resource(signed_url, filename)
                        if analysis:
                            logger.info("[StyleExtract] image analysis: file=%s analysis=%s", filename, analysis)
                    resource_manifest.append({
                        "filename": filename,
                        "url": img_url,
                        "used_in_slides": res["slides"],
                        "usage_type": res.get("usage_type", "image"),
                        "usage_types": res.get("usage_types", []),
                        "description": analysis or {},
                    })

                resource_section = _build_resource_section(resource_manifest)
                markdown_text = markdown_text.rstrip() + "\n\n" + resource_section
                logger.info("[StyleExtract] appended resource section: %d resources, md_len=%d", len(resource_manifest), len(markdown_text))
            else:
                logger.info("[StyleExtract] no background resources found")

            # --- Step 2-3: Agent Graph — Style Template + Preview HTML ---
            await self._check_cancel(cancel_event)
            await self._update_progress(task_id, "analyzing_style", pptx_filename=pptx_filename)

            async def _before_preview(state: dict):
                await self._check_cancel(cancel_event)
                await self._update_progress(
                    task_id,
                    "generating_preview",
                    pptx_filename=pptx_filename,
                    description=state.get("description", ""),
                    style_description=state.get("style_description", ""),
                    style_name=state.get("style_name", ""),
                    style_name_en=state.get("style_name_en", ""),
                )

            style_graph = create_style_extract_graph(
                self._text_llm,
                self._prompt_manager,
                on_before_preview=_before_preview,
            )
            graph_result = await style_graph.ainvoke({
                "markdown_text": markdown_text,
                "resource_base_url": resource_base_url,
                "resource_manifest": resource_manifest,
            })

            raw_style_output = graph_result.get("raw_style_output", "")
            style_name = graph_result.get("style_name") or "未命名风格"
            style_name_en = graph_result.get("style_name_en") or resolve_style_name_en("", style_name)
            description = graph_result.get("description", "")
            style_description = graph_result.get("style_description", "")
            preview_html = graph_result.get("preview_html", "")
            style_validation_errors = graph_result.get("style_validation_errors", [])
            preview_validation_errors = graph_result.get("preview_validation_errors", [])
            if style_validation_errors or preview_validation_errors:
                logger.warning(
                    "[StyleExtract] graph validation warnings task=%s style=%s preview=%s",
                    task_id,
                    style_validation_errors,
                    preview_validation_errors,
                )

            logger.info(f"[StyleExtract] STYLE_TEMPLATE task={task_id} style_template={raw_style_output}")
            logger.info(f"[StyleExtract] PREVIEW_HTML task={task_id}")

            # --- Step 4: Save & Complete ---
            await self._check_cancel(cancel_event)

            # Save preview HTML to: user/{user_id}/workspace/{workspace_id}/style/{task_id}/preview.html
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
                "progress_step": "completed",
            }
            await self.db.update_task(
                task_id,
                status="completed",
                title=style_name,
                result_data=json.dumps(result_data, ensure_ascii=False),
            )
            logger.info("[StyleExtract] COMPLETED task=%s style_name=%s", task_id, style_name)

        except _CancelledError:
            logger.info("[StyleExtract] task=%s cancelled", task_id)
            await self.db.update_task(task_id, status="cancelled")
        except Exception as exc:
            logger.error("[StyleExtract] task=%s failed: %s", task_id, exc, exc_info=True)
            error_data = {"error": str(exc), "pptx_filename": pptx_filename, "progress_step": "failed"}
            await self.db.update_task(
                task_id, status="failed",
                result_data=json.dumps(error_data, ensure_ascii=False),
            )
        finally:
            self._active_tasks.pop(task_id, None)

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
            raise ValueError(f"Task not found: {task_id}")
        if task["status"] != "completed":
            raise ValueError(f"Task not completed: {task_id} (status={task['status']})")

        result_data = task.get("result_data")
        if isinstance(result_data, str):
            result_data = json.loads(result_data)
        if not result_data:
            raise ValueError(f"Task has no result_data: {task_id}")

        # Duplicate save check
        if result_data.get("saved_style_id"):
            raise ValueError("该风格已保存，请勿重复操作")

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
            old_resource_base = f"{resource_prefix}/resource/"
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
