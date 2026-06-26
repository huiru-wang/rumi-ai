import logging
from pathlib import Path

logger = logging.getLogger(__name__)

# Directory containing prompt template files
_PROMPTS_DIR = Path(__file__).resolve().parent / "prompts"

# ============================================================
# RumiAI System Prompt (loaded from file via PromptManager)
# ============================================================

_FALLBACK_SYSTEM_PROMPT = "你是 RumiAI，一个文档驱动的 AI 工作台助手，基于知识库文档为用户提供问答与内容生成服务。"


class PromptManager:
    """统一管理所有 prompt 模板的构建。"""

    def __init__(self):
        self._viewport_css: str | None = None
        self._style_prompt_template: str | None = None
        self._cover_html_prompt_template: str | None = None
        self._system_prompt: str | None = None

    # ------------------------------------------------------------------
    # Lazy loaders for prompt templates
    # ------------------------------------------------------------------

    def _get_system_prompt(self) -> str:
        if self._system_prompt is None:
            path = _PROMPTS_DIR / "system_prompt.md"
            try:
                self._system_prompt = path.read_text(encoding="utf-8").strip()
                logger.info("[PromptManager] loaded system prompt from %s (%d chars)", path, len(self._system_prompt))
            except FileNotFoundError:
                logger.error("[PromptManager] system_prompt.md not found at %s, using fallback", path)
                self._system_prompt = _FALLBACK_SYSTEM_PROMPT
        return self._system_prompt

    def _get_viewport_css(self) -> str:
        if self._viewport_css is None:
            css_path = Path(__file__).resolve().parent.parent.parent / "skills" / "ppt" / "assets" / "viewport-base.css"
            try:
                self._viewport_css = css_path.read_text(encoding="utf-8")
            except FileNotFoundError:
                logger.warning("[PromptManager] viewport-base.css not found at %s", css_path)
                self._viewport_css = "/* viewport-base.css not found */"
        return self._viewport_css

    def _get_style_prompt_template(self) -> str:
        if self._style_prompt_template is None:
            path = _PROMPTS_DIR / "style_extract_prompt.md"
            try:
                self._style_prompt_template = path.read_text(encoding="utf-8")
            except FileNotFoundError:
                logger.warning("[PromptManager] style_extract_prompt.md not found at %s", path)
                self._style_prompt_template = "# ERROR: style_extract_prompt.md not found"
        return self._style_prompt_template

    def _get_cover_html_prompt_template(self) -> str:
        if self._cover_html_prompt_template is None:
            path = _PROMPTS_DIR / "generate_cover_html_prompt.md"
            try:
                self._cover_html_prompt_template = path.read_text(encoding="utf-8")
            except FileNotFoundError:
                logger.warning("[PromptManager] generate_cover_html_prompt.md not found at %s", path)
                self._cover_html_prompt_template = "# ERROR: generate_cover_html_prompt.md not found"
        return self._cover_html_prompt_template

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def get_system_prompt(self) -> str:
        """获取 Agent 的静态 system prompt（从 prompts/system_prompt.md 加载）。"""
        return self._get_system_prompt()

    def build_style_description_prompt(self, markdown_text: str) -> str:
        """构建风格描述 system prompt。

        Args:
            markdown_text: PPTX 解析后的精准 Markdown 结构报告
        """
        template = self._get_style_prompt_template()
        return (
            f"{template}\n\n"
            f"---\n\n"
            f"## PPTX 结构化解析报告\n\n"
            f"{markdown_text}\n"
        )

    def build_preview_html_prompt(
        self,
        style_template: str,
        resource_base_url: str = "",
        resource_manifest: list[dict] | None = None,
    ) -> str:
        """构建预览 HTML 生成 system prompt。

        Args:
            style_template: 完整的风格模板 Markdown（即 style_description，纯正文，不含 frontmatter）
            resource_base_url: 图片资源的基础 URL（无 resource_manifest 时的 fallback）
            resource_manifest: 资源清单，包含文件名、URL 和使用建议
        """
        template = self._get_cover_html_prompt_template()
        parts = [
            template,
            "",
            "---",
            "",
            f"=== 风格模版（完整内容，必须严格遵循） ===\n{style_template}",
        ]

        if resource_manifest:
            lines = [
                "",
                "=== 视觉资产（资源清单） ===",
                "",
                "以下资源**必须**用于封面页背景（按「使用建议」应用）。",
                "",
                "| 文件 | URL | 使用建议 |",
                "|------|-----|----------|",
            ]
            for res in resource_manifest:
                fn = res.get("filename", "")
                url = res.get("url", "")
                desc = res.get("description", {})
                notes = desc.get("usage_notes", "") if isinstance(desc, dict) else ""
                lines.append(f"| {fn} | `{url}` | {notes} |")
            parts.extend(lines)
        else:
            parts.extend([
                "",
                f"=== 图片资源基础 URL ===\n{resource_base_url or '（无外部图片资源）'}",
            ])

        return "\n".join(parts)
