import json
import logging

from langchain.tools import tool, ToolRuntime

from src.agent.state import MainAgentState
from src.storage.database import Database

logger = logging.getLogger(__name__)


def create_get_ppt_detail_tool(db: Database):
    @tool
    async def get_ppt_detail(
        runtime: ToolRuntime[MainAgentState],
        task_id: str,
        **kwargs,
    ) -> str:
        """获取指定 PPT 任务的详细信息，包括结构化大纲、风格、文件路径等。
        用于生成口播稿时获取幻灯片结构和关键词。

        Args:
            task_id: PPT 任务的 ID
        """
        logger.info("[Tool:get_ppt_detail] task_id=%s", task_id)

        task = await db.get_task(task_id)
        if not task:
            return f"未找到 ID 为 {task_id} 的任务。请检查任务 ID 是否正确。"

        if task.get("type") != "ppt":
            return f"任务 {task_id} 不是 PPT 类型（类型: {task.get('type')}）。口播稿生成仅支持 PPT 类型任务。"

        result_data = {}
        if task.get("result_data"):
            try:
                result_data = json.loads(task["result_data"])
            except (json.JSONDecodeError, TypeError):
                pass

        title = task.get("title", "未知标题")
        ppt_style = result_data.get("ppt_style", "未知")
        file_path = result_data.get("file_path", "")
        outline = result_data.get("outline")

        if not outline:
            return (
                f"PPT 标题：{title}\n"
                f"风格：{ppt_style}\n"
                f"文件路径：{file_path}\n\n"
                f"⚠️ 该 PPT 任务未保存结构化大纲信息。"
                f"你需要直接阅读 HTML 文件内容来了解幻灯片结构，口播稿质量可能受限。"
            )

        # Format outline as readable text
        lines = [
            f"PPT 标题：{outline.get('title', title)}",
        ]
        if outline.get("topic"):
            lines.append(f"主题：{outline['topic']}")
        if outline.get("summary"):
            lines.append(f"摘要：{outline['summary']}")
        lines.extend([
            f"风格：{outline.get('style', ppt_style)}",
            f"目标受众：{outline.get('audience', '未指定')}",
            f"用途：{outline.get('purpose', '未指定')}",
            f"总页数：{outline.get('total_slides', len(outline.get('slides', [])))}",
            f"文件路径：{file_path}",
            "",
            "=== 幻灯片结构 ===",
            "",
        ])

        for slide in outline.get("slides", []):
            num = slide.get("number", "?")
            slide_title = slide.get("title", "无标题")
            key_points = slide.get("key_points", [])
            keywords = slide.get("keywords", [])
            source_refs = slide.get("source_refs", [])
            notes = slide.get("notes", "")

            lines.append(f"第 {num} 页：{slide_title}")
            if key_points:
                lines.append(f"  要点：{', '.join(key_points)}")
            if keywords:
                lines.append(f"  关键词：{', '.join(keywords)}")
            if source_refs:
                lines.append(f"  来源引用：{', '.join(source_refs)}")
            if notes:
                lines.append(f"  备注：{notes}")
            lines.append("")

        logger.info(
            "[get_ppt_detail] title=%s, slides=%d",
            title, len(outline.get("slides", [])),
        )
        return "\n".join(lines)

    return get_ppt_detail
