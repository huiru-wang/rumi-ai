import json
import logging

from langchain.tools import tool, ToolRuntime

from src.agent.state import MainAgentState
from src.storage.database import Database

logger = logging.getLogger(__name__)


def create_get_style_template_tool(db: Database):
    @tool
    async def get_style_template(
        runtime: ToolRuntime[MainAgentState],
        **kwargs,
    ) -> str:
        """获取当前配置的 PPT 风格模版完整内容（风格描述 + 资源清单）。

        生成 PPT 前必须调用此工具，获取完整的风格规范，包括：
        - 颜色体系、字体规范、布局规则、背景图片使用方式等详细描述
        - 可用的背景图片、装饰素材等资源清单（含 URL 和使用建议）

        无需传入任何参数，工具会自动从当前配置中读取风格 ID。
        """
        style_id = runtime.state.get("ppt_style", "")
        logger.info("[Tool:get_style_template] ppt_style=%s", style_id)

        if not style_id:
            return _fallback_message("当前未配置 PPT 风格，将使用默认风格 Swiss Modern。")

        # Look up by id first; fallback to name_en for legacy data
        style_record = None
        try:
            style_record = await db.get_ppt_style(style_id)
            if not style_record:
                # Legacy data: ppt_style may be name_en instead of id
                ws = await db.get_workspace(runtime.state.get("workspace_id", "default"))
                user_id = ws.get("user_id", "") if ws else ""
                style_record = await db.get_ppt_style_by_name_en(style_id, user_id=user_id)
        except Exception:
            logger.warning("[Tool:get_style_template] failed to query ppt_style=%s", style_id, exc_info=True)

        if not style_record:
            return _fallback_message(
                f"未找到 ID 为 {style_id} 的风格模版，将使用默认风格 Swiss Modern。"
            )

        return _build_template_text(style_record)

    return get_style_template


def _build_template_text(record: dict) -> str:
    """将 style_record 拼接为完整的风格模版文本。"""
    name = record.get("name", "")
    name_en = record.get("name_en", "")
    description = record.get("description", "")
    style_desc = record.get("style_description", "")

    lines = [
        f"# PPT 风格模版：{name}（{name_en}）",
        "",
        f"> {description}" if description else "",
        "",
    ]

    # style_description body
    if style_desc:
        lines.append(style_desc)
    else:
        lines.append("⚠️ 该风格模版暂无详细描述。")

    # resource_manifest
    resource_manifest_raw = record.get("resource_manifest")
    if resource_manifest_raw:
        try:
            resource_manifest = (
                json.loads(resource_manifest_raw)
                if isinstance(resource_manifest_raw, str)
                else resource_manifest_raw
            )
        except (json.JSONDecodeError, TypeError):
            resource_manifest = []

        if resource_manifest:
            lines.append("")
            lines.append("## 视觉资产（资源清单）")
            lines.append("")
            lines.append("以下资源必须严格按照「使用建议」应用到对应的幻灯片场景中。")
            lines.append("")
            lines.append("| 文件 | URL | 使用建议 |")
            lines.append("|------|-----|----------|")
            for res in resource_manifest:
                fn = res.get("filename", "")
                url = res.get("url", "")
                desc = res.get("description", {})
                notes = desc.get("usage_notes", "") if isinstance(desc, dict) else ""
                lines.append(f"| {fn} | `{url}` | {notes} |")

    return "\n".join(lines)


def _fallback_message(msg: str) -> str:
    return msg
