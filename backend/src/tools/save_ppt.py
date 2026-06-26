import json
import logging
import re

from langchain.tools import tool, ToolRuntime

from src.agent.state import MainAgentState
from src.limits import MAX_PPT_TASKS_PER_WORKSPACE
from src.storage.database import Database
from src.storage.file_store import FileStore

logger = logging.getLogger(__name__)

# Patterns for RAG source attribution markers that must not appear in PPT HTML
_REF_PATTERNS = [
    # {{ref:filename|chapter}} or {ref:filename|chapter}
    re.compile(r'\{1,2\s*ref:[^}]*\}{1,2}'),
    # ref:filename|chapter (standalone, e.g. in slide text)
    re.compile(r'ref:[^\s<>"]+\|[^\s<>"]+'),
    # [片段N] prefix from RAG tool output
    re.compile(r'\[片段\d+\]\s*'),
    # 📄 filename | location (source header from RAG tool)
    re.compile(r'📄\s*[^|\n<]+\|\s*[^\n<]+'),
]


def _strip_ref_markers(html: str) -> str:
    """Remove RAG source attribution markers from HTML content as a safety net."""
    for pattern in _REF_PATTERNS:
        html = pattern.sub('', html)
    return html


async def save_ppt_artifact(
    db: Database,
    file_store: FileStore,
    workspace_id: str,
    title: str,
    content: str,
    filename: str = "",
    ppt_style: str = "",
    outline: str = "",
) -> tuple[dict, str]:
    """Save a PPT artifact to the file store and create a task record in DB."""
    # Quota check: max PPT tasks per workspace
    ppt_count = await db.count_tasks_by_type(workspace_id, "ppt")
    if ppt_count >= MAX_PPT_TASKS_PER_WORKSPACE:
        return (
            {},
            f"保存失败：每个工作区最多生成 {MAX_PPT_TASKS_PER_WORKSPACE} 个PPT任务，当前已有 {ppt_count} 个。请删除旧任务后重试。",
        )

    # Always derive filename from title (Chinese) to ensure readable download names.
    # The LLM may pass an English filename — ignore it in favor of the user-visible title.
    safe_title = title.replace(" ", "_").replace("/", "_").replace("\\", "_")
    filename = f"{safe_title}.html"

    task = await db.create_task(
        workspace_id=workspace_id, type="ppt", title=title
    )
    logger.info("[save_ppt] task created: id=%s, title=%s", task["id"], title)

    try:
        # Safety net: strip RAG source attribution markers that must not appear in PPT HTML
        cleaned = _strip_ref_markers(content)
        if cleaned != content:
            logger.warning("[save_ppt] stripped RAG reference markers from HTML content")
            content = cleaned

        content_bytes = content.encode("utf-8")
        file_path = await file_store.save_ppt_file(
            workspace_id,
            task["id"],
            filename,
            content_bytes,
        )
        logger.info("[save_ppt] file saved: %s (%d bytes)", file_path, len(content_bytes))

        result_data = {
            "file_path": file_path,
            "filename": filename,
            "ppt_style": ppt_style,
        }

        # Look up style name for display (best-effort, never block saving)
        if ppt_style:
            try:
                style_record = await db.get_ppt_style(ppt_style)
                if not style_record:
                    style_record = await db.get_ppt_style_by_name_en(ppt_style)
                if style_record:
                    result_data["ppt_style_name"] = style_record["name"]
            except Exception:
                logger.warning("[save_ppt] failed to look up style name for ppt_style=%s", ppt_style, exc_info=True)

        # Parse and include outline if provided
        if outline:
            try:
                result_data["outline"] = json.loads(outline) if isinstance(outline, str) else outline
            except (json.JSONDecodeError, TypeError):
                logger.warning("[save_ppt] failed to parse outline JSON, storing as string")
                result_data["outline"] = outline

        await db.update_task(
            task["id"],
            status="completed",
            result_data=json.dumps(result_data, ensure_ascii=False),
        )
        return task, f"产出已保存: {title}。用户可在右侧产出面板查看和下载。"

    except Exception as exc:
        await db.update_task(
            task["id"],
            status="failed",
            result_data=json.dumps({"error": str(exc), "filename": filename}),
        )
        logger.error("[save_ppt] failed: %s", exc, exc_info=True)
        return task, f"产出保存失败: {exc}"


def create_save_ppt_tool(db: Database, file_store: FileStore):
    @tool
    async def save_ppt(
        runtime: ToolRuntime[MainAgentState],
        title: str,
        content: str,
        filename: str = "",
        outline: str = "",
        **kwargs,
    ) -> str:
        """保存 PPT 产出物。这是将 PPT 交付给用户的唯一方式。

        调用后，产出物会出现在用户的右侧产出面板中，可预览和下载。
        你必须在完成 PPT 内容后调用此工具，否则用户无法获取结果。

        Args:
            title: PPT 标题
            content: 完整的自包含 HTML 内容
            filename: 文件名（可选，默认根据 title 自动生成 .html）
            outline: 结构化大纲 JSON 字符串，包含 slides 数组（每个 slide 含 number/title/key_points/keywords）
        """
        workspace_id = runtime.state.get("workspace_id", "default")
        ppt_style = runtime.state.get("ppt_style", "")
        logger.info(
            "[save_ppt] title=%s, content_len=%d, workspace=%s, style=%s, outline_len=%d",
            title, len(content), workspace_id, ppt_style, len(outline),
        )

        _, message = await save_ppt_artifact(
            db=db,
            file_store=file_store,
            workspace_id=workspace_id,
            title=title,
            content=content,
            filename=filename,
            ppt_style=ppt_style,
            outline=outline,
        )
        return message

    return save_ppt
