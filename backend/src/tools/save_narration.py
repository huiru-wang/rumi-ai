import asyncio
import json
import logging
import re
import traceback

from langchain.tools import tool, ToolRuntime

from src.agent.state import MainAgentState
from src.limits import MAX_NARRATIONS_PER_PPT_TASK
from src.managers.tts_manager import TTSManager
from src.storage.database import Database
from src.storage.seeds import _BUILTIN_VOICES
from src.storage.file_store import FileStore

logger = logging.getLogger(__name__)

# Patterns for RAG source attribution markers that must not appear in narration text
_REF_PATTERNS = [
    re.compile(r'\{1,2\s*ref:[^}]*\}{1,2}'),
    re.compile(r'ref:[^\s<>"]+\|[^\s<>"]+'),
    re.compile(r'\[片段\d+\]\s*'),
    re.compile(r'📄\s*[^|\n<]+\|\s*[^\n<]+'),
]


def _strip_ref_markers(text: str) -> str:
    """Remove RAG source attribution markers from narration text as a safety net."""
    for pattern in _REF_PATTERNS:
        text = pattern.sub('', text)
    return text


async def _tts_pipeline(
    db: Database,
    file_store: FileStore,
    tts_service: TTSManager,
    task_id: str,
    parent_task_id: str,
    workspace_id: str,
    slides: list[dict],
    voice: str,
):
    """Serial TTS generation pipeline: process slides one by one, updating result_data after each."""

    try:
        for slide in slides:
            num = slide["number"]
            text = slide.get("text", "")

            if not text.strip():
                logger.warning("[save_narration] slide %d has empty text, skipping TTS", num)
                continue

            logger.info("[save_narration] TTS slide %d: text_len=%d, voice=%s", num, len(text), voice)
            audio_bytes = await tts_service.synthesize(text=text, voice=voice)

            filename = f"{task_id}_narration_{num}.wav"
            file_path = await file_store.save_ppt_file(
                workspace_id, parent_task_id, filename, audio_bytes
            )
            logger.info("[save_narration] slide %d audio saved: %s (%d bytes)", num, file_path, len(audio_bytes))

            # Update result_data after each slide (for progress tracking)
            current = await db.get_task_result_data(task_id)
            # Write audio_path into the corresponding slide entry
            for s in current.get("slides", []):
                if s.get("number") == num:
                    s["audio_path"] = file_path
                    break
            current["tts_progress"] = num
            await db.update_task(
                task_id,
                result_data=json.dumps(current, ensure_ascii=False),
            )

        # All slides completed
        await db.update_task(task_id, status="completed")
        logger.info("[save_narration] TTS pipeline completed for task %s", task_id)

    except Exception as exc:
        tb = traceback.format_exc()
        logger.error(
            "[save_narration] TTS pipeline failed at slide %s: %s: %s\n%s",
            num, type(exc).__name__, exc, tb,
        )
        try:
            current = await db.get_task_result_data(task_id)
            current["tts_error"] = f"Slide {num} TTS failed: {type(exc).__name__}: {exc}"
            await db.update_task(
                task_id,
                status="tts_failed",
                result_data=json.dumps(current, ensure_ascii=False),
            )
        except Exception as update_exc:
            logger.error("[save_narration] failed to update task status: %s", update_exc)


def create_save_narration_tool(db: Database, file_store: FileStore, tts_service: TTSManager):
    @tool
    async def save_narration(
        runtime: ToolRuntime[MainAgentState],
        parent_task_id: str,
        title: str,
        slides: str,
        language: str = "zh",
        **kwargs,
    ) -> str:
        """保存口播稿并触发 TTS 音频生成。

        调用后，口播稿文本和音频会作为子任务出现在产出面板中。
        文本立即保存，音频在后台串行生成，逐页更新进度。

        Args:
            parent_task_id: 关联的 PPT 任务 ID
            title: 口播稿标题
            slides: JSON 字符串，格式为 [{"number":1, "title":"...", "text":"口播稿文本"}, ...]
            language: 语言代码 — 'zh'（中文）或 'en'（英文）
        """
        workspace_id = runtime.state.get("workspace_id", "default")
        # Voice: always from MainAgentState, fallback to workspace ext_data
        voice_id = runtime.state.get("voice_id", "")
        if not voice_id:
            ws = await db.get_workspace(workspace_id)
            ext_data = ws.get("ext_data", {}) or {}
            voice_info = ext_data.get("voice_info", {})
            voice_id = voice_info.get("id", "Cherry") if isinstance(voice_info, dict) else "Cherry"

        # Look up voice display name from builtin seed data
        voice_name = ""
        for v in _BUILTIN_VOICES:
            if v["id"] == voice_id:
                voice_name = v["name"]
                break

        logger.info(
            "[save_narration] parent=%s, title=%s, language=%s, voice_id=%s, workspace=%s",
            parent_task_id, title, language, voice_id, workspace_id,
        )

        # Validate parent task
        parent_task = await db.get_task(parent_task_id)
        if not parent_task:
            return f"错误：未找到 PPT 任务 {parent_task_id}。"
        if parent_task.get("type") != "ppt":
            return f"错误：任务 {parent_task_id} 不是 PPT 类型。"

        # Quota check: max narrations per PPT task
        narration_count = await db.count_child_tasks(parent_task_id, "narration")
        if narration_count >= MAX_NARRATIONS_PER_PPT_TASK:
            return (
                f"错误：每个PPT任务最多生成 {MAX_NARRATIONS_PER_PPT_TASK} 个口播稿，"
                f"当前已有 {narration_count} 个。请删除旧口播稿后重试。"
            )

        # Parse slides JSON
        try:
            slides_list = json.loads(slides) if isinstance(slides, str) else slides
        except (json.JSONDecodeError, TypeError):
            return "错误：slides 参数不是有效的 JSON 格式。"

        if not slides_list:
            return "错误：slides 列表为空。"

        # Build narration markdown text
        md_lines = [f"# {title}\n"]
        for slide in slides_list:
            num = slide.get("number", "?")
            slide_title = slide.get("title", "")
            text = slide.get("text", "")
            # Safety net: strip RAG source attribution markers
            text = _strip_ref_markers(text)
            md_lines.append(f"## 【第{num}页：{slide_title}】\n")
            md_lines.append(f"{text}\n")

        narration_md = "\n".join(md_lines)

        # Create narration task
        task = await db.create_task(
            workspace_id=workspace_id,
            type="narration",
            title=title,
            parent_task_id=parent_task_id,
        )
        logger.info("[save_narration] task created: id=%s", task["id"])

        # Save narration text file under ppt/{parent_task_id}/
        text_filename = f"{task['id']}_narration.md"
        text_file_path = await file_store.save_ppt_file(
            workspace_id,
            parent_task_id,
            text_filename,
            narration_md.encode("utf-8"),
        )
        logger.info("[save_narration] text saved: %s", text_file_path)

        # Write initial result_data (audio_path per slide starts as null)
        for s in slides_list:
            s["audio_path"] = None
        result_data = {
            "slides": slides_list,
            "language": language,
            "voice_id": voice_id,
            "voice_name": voice_name,
            "text_file_path": text_file_path,
            "text_filename": text_filename,
            "tts_progress": 0,
        }
        await db.update_task(
            task["id"],
            result_data=json.dumps(result_data, ensure_ascii=False),
        )

        # Trigger async TTS pipeline
        if tts_service.is_configured:
            await db.update_task(task["id"], status="tts_generating")
            asyncio.create_task(
                _tts_pipeline(
                    db=db,
                    file_store=file_store,
                    tts_service=tts_service,
                    task_id=task["id"],
                    parent_task_id=parent_task_id,
                    workspace_id=workspace_id,
                    slides=slides_list,
                    voice=voice_id,
                )
            )
            tts_msg = "，TTS 音频正在后台生成"
        else:
            await db.update_task(task["id"], status="completed")
            tts_msg = "（TTS 未配置，仅保存文本）"

        return (
            f"口播稿已保存: {title}{tts_msg}。"
            f"共 {len(slides_list)} 页，用户可在产出面板查看进度和下载。"
        )

    return save_narration
