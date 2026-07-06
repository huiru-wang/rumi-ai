"""LangGraph pipeline for PPT style extraction.

The manager owns file IO, parsing, progress updates, and persistence. This
graph owns the LLM-facing extraction chain: asset inventory, page-layout
inventory, style template generation, validation/repair, preview generation,
and preview validation/repair.
"""

from __future__ import annotations

import hashlib
import re
from collections.abc import Awaitable, Callable
from typing import Any, TypedDict

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI
from langgraph.graph import END, START, StateGraph

from src.managers.prompt_manager import PromptManager


class StyleExtractionState(TypedDict, total=False):
    markdown_text: str
    resource_base_url: str
    resource_manifest: list[dict[str, Any]]
    asset_inventory: str
    layout_inventory: str
    raw_style_output: str
    style_name: str
    style_name_en: str
    description: str
    style_description: str
    style_validation_errors: list[str]
    style_repair_attempts: int
    raw_preview_html: str
    preview_html: str
    preview_validation_errors: list[str]
    preview_repair_attempts: int


ProgressCallback = Callable[[StyleExtractionState], Awaitable[None]]


def parse_frontmatter(llm_output: str) -> dict[str, str]:
    """Parse YAML frontmatter from LLM-generated Markdown."""
    output = llm_output.strip()
    if output.startswith("---"):
        rest = output[3:].lstrip("\n")
        end_idx = rest.find("\n---")
        if end_idx != -1:
            frontmatter_text = rest[:end_idx]
            body = rest[end_idx + 4:].lstrip("\n")

            name = ""
            name_en = ""
            description = ""
            for line in frontmatter_text.split("\n"):
                line = line.strip()
                if line.startswith("name:") and "name_en" not in line[:7]:
                    name = line[len("name:"):].strip().strip("\"'")
                elif line.startswith("name_en:"):
                    name_en = line[len("name_en:"):].strip().strip("\"'")
                elif line.startswith("description:"):
                    description = line[len("description:"):].strip().strip("\"'")

            return {
                "name": name,
                "name_en": name_en,
                "description": description,
                "style_description": body.strip(),
            }

    return {
        "name": "",
        "name_en": "",
        "description": "",
        "style_description": output,
    }


def resolve_style_name_en(name_en: str, name: str) -> str:
    """Ensure name_en is valid kebab-case. Generate fallback if needed."""
    if name_en:
        name_en = re.sub(r"[^a-zA-Z0-9\s-]", "", name_en).strip().lower()
        name_en = re.sub(r"\s+", "-", name_en)

    if not name_en or not re.search(r"[a-z]", name_en):
        fallback = name or "unnamed"
        short_hash = hashlib.md5(fallback.encode()).hexdigest()[:6]
        name_en = f"style-{short_hash}"

    return name_en


def strip_code_fence(text: str) -> str:
    """Remove markdown code fences around generated HTML."""
    stripped = text.strip()
    if stripped.startswith("```"):
        stripped = re.sub(r"^```[a-zA-Z0-9_-]*\s*\n?", "", stripped)
        stripped = re.sub(r"\n?```\s*$", "", stripped)
    return stripped.strip()


def _extract_slide_blocks(markdown_text: str) -> list[tuple[int, str]]:
    matches = list(re.finditer(r"^## 第 (\d+) 页\s*$", markdown_text, re.M))
    blocks: list[tuple[int, str]] = []
    for idx, match in enumerate(matches):
        start = match.end()
        end = matches[idx + 1].start() if idx + 1 < len(matches) else len(markdown_text)
        blocks.append((int(match.group(1)), markdown_text[start:end]))
    return blocks


def build_asset_inventory(resource_manifest: list[dict[str, Any]]) -> str:
    if not resource_manifest:
        return "## 视觉资产盘点\n\n- 未提取到外部视觉资源；预览可使用 CSS 图形、渐变和纹理构建。"

    lines = [
        "## 视觉资产盘点",
        "",
        f"- 资源总数：{len(resource_manifest)}",
        "- 规则：保留能定义风格的背景图、关键插画、图标与装饰图形；弱业务截图或低质量素材可降级为参考。",
        "",
        "| 文件 | 类型 | 使用页 | URL | 使用建议 |",
        "|------|------|--------|-----|----------|",
    ]
    for res in resource_manifest:
        slides = ", ".join(str(s) for s in res.get("used_in_slides", [])) or "-"
        desc = res.get("description", {})
        notes = desc.get("usage_notes", "") if isinstance(desc, dict) else ""
        lines.append(
            f"| {res.get('filename', '')} | {res.get('usage_type', 'image')} | {slides} | "
            f"`{res.get('url', '')}` | {notes or '按页面类型判断是否使用'} |"
        )
    return "\n".join(lines)


def build_layout_inventory(markdown_text: str) -> str:
    slide_blocks = _extract_slide_blocks(markdown_text)
    total = len(slide_blocks)
    lines = [
        "## 页面布局盘点",
        "",
        "- 固定 page_type 只能是：cover / agenda / section / content / closing。",
        "- 下面是机器预判，LLM 需要结合原报告修正，但不得创造业务相关 page_type。",
        "",
        "| 页码 | 建议 page_type | 图片数 | 文本块数 | 布局线索 |",
        "|------|----------------|--------|----------|----------|",
    ]
    for slide_no, block in slide_blocks:
        image_count = len(re.findall(r"(?:\.\./)?media/[\w.-]+\.\w+|/resource/[\w.-]+\.\w+", block))
        text_count = max(0, block.count("| sp |") + block.count("| graphicFrame |") + block.count("| grpSp |"))
        if slide_no == 1:
            page_type = "cover"
        elif total > 1 and slide_no == total:
            page_type = "closing"
        elif re.search(r"(目录|agenda|contents|table of contents)", block, re.I):
            page_type = "agenda"
        elif text_count <= 3 and image_count <= 2:
            page_type = "section"
        else:
            page_type = "content"

        if image_count >= 3:
            clue = "多图/图标阵列"
        elif image_count == 1:
            clue = "单图视觉锚点"
        elif text_count >= 6:
            clue = "密集文本或卡片"
        else:
            clue = "标题/少量要点"
        lines.append(f"| {slide_no} | {page_type} | {image_count} | {text_count} | {clue} |")

    return "\n".join(lines)


def _validate_style_description(style_description: str, style_name: str, description: str) -> list[str]:
    errors: list[str] = []
    if not style_name or style_name == "未命名风格":
        errors.append("缺少可用的中文风格名")
    if not description:
        errors.append("frontmatter 缺少 description")
    if "page_layouts:" not in style_description:
        errors.append("Layout Grammar 缺少标准化 page_layouts")
    if "section_policy:" not in style_description:
        errors.append("缺少 section_policy")
    for page_type, display_name in (
        ("cover:", "display_name: 封面页"),
        ("agenda:", "display_name: 目录页"),
        ("section:", "display_name: 章节页"),
        ("content:", "display_name: 内容页"),
        ("closing:", "display_name: 封底页"),
    ):
        if page_type not in style_description:
            errors.append(f"page_layouts 缺少 {page_type.rstrip(':')}")
        if display_name not in style_description:
            errors.append(f"{page_type.rstrip(':')} 缺少中文 display_name")
    if "```" in style_description:
        errors.append("风格模板正文不能包含代码块")
    return errors


def _extract_enabled_page_types(style_description: str) -> list[str]:
    enabled: list[str] = []
    lines = style_description.splitlines()
    for page_type in ("cover", "agenda", "section", "content", "closing"):
        start_idx = next(
            (
                idx for idx, line in enumerate(lines)
                if re.match(rf"^\s{{2}}{page_type}:\s*$", line)
            ),
            None,
        )
        if start_idx is None:
            continue
        block: list[str] = []
        for line in lines[start_idx + 1:]:
            if re.match(r"^\s{2}(cover|agenda|section|content|closing):\s*$", line):
                break
            block.append(line)
        if any(re.match(r"^\s+enabled:\s*true\s*$", line) for line in block):
            enabled.append(page_type)
    return enabled or ["cover", "content"]


def _validate_preview_html(preview_html: str, style_description: str) -> list[str]:
    errors: list[str] = []
    if "<!DOCTYPE html>" not in preview_html[:200]:
        errors.append("预览 HTML 缺少 <!DOCTYPE html>")
    if "contenteditable" in preview_html.lower():
        errors.append("预览 HTML 不能包含 contenteditable")
    if "localStorage" in preview_html or "InlineEditor" in preview_html:
        errors.append("预览 HTML 不能包含编辑/保存脚本")
    slide_count = len(re.findall(r"<section\b[^>]*class=[\"'][^\"']*\bslide\b", preview_html))
    enabled_types = _extract_enabled_page_types(style_description)
    if slide_count < max(2, len(enabled_types)):
        errors.append(f"预览页数不足，应覆盖启用页面类型：{', '.join(enabled_types)}")
    for page_type in enabled_types:
        if f"data-page-type=\"{page_type}\"" not in preview_html and f"page-type-{page_type}" not in preview_html:
            errors.append(f"预览 HTML 未标记或覆盖页面类型 {page_type}")
    if "reveal" not in preview_html or ".visible" not in preview_html:
        errors.append("预览 HTML 缺少入场动画 reveal/visible")
    if "data-preview-mode=\"readonly\"" not in preview_html and "contenteditable=\"false\"" not in preview_html:
        errors.append("预览 HTML 缺少只读预览标记")
    return errors


async def _invoke_text(llm: ChatOpenAI, system: str, user: str) -> str:
    response = await llm.ainvoke([
        SystemMessage(content=system),
        HumanMessage(content=user),
    ])
    if isinstance(response, AIMessage):
        content = response.content
        if isinstance(content, str):
            return content
        if isinstance(content, list):
            return "".join(
                part.get("text", "") if isinstance(part, dict) else str(part)
                for part in content
            )
    return str(response.content)


def create_style_extract_graph(
    llm: ChatOpenAI,
    prompt_manager: PromptManager | None = None,
    on_before_preview: ProgressCallback | None = None,
):
    """Create the style extraction graph."""
    prompt_manager = prompt_manager or PromptManager()

    async def asset_inventory(state: StyleExtractionState) -> dict[str, Any]:
        return {"asset_inventory": build_asset_inventory(state.get("resource_manifest", []))}

    async def layout_inventory(state: StyleExtractionState) -> dict[str, Any]:
        return {"layout_inventory": build_layout_inventory(state.get("markdown_text", ""))}

    async def generate_style(state: StyleExtractionState) -> dict[str, Any]:
        enriched_markdown = "\n\n".join(
            part for part in (
                state.get("markdown_text", ""),
                state.get("asset_inventory", ""),
                state.get("layout_inventory", ""),
            )
            if part
        )
        system_prompt = prompt_manager.build_style_description_prompt(
            enriched_markdown
        )
        raw_style_output = await _invoke_text(
            llm,
            system_prompt,
            "请根据以上 PPTX 结构化解析报告，生成风格模版。",
        )
        parsed = parse_frontmatter(raw_style_output)
        style_name = parsed["name"] or "未命名风格"
        style_name_en = resolve_style_name_en(parsed["name_en"], style_name)
        return {
            "raw_style_output": raw_style_output,
            "style_name": style_name,
            "style_name_en": style_name_en,
            "description": parsed["description"],
            "style_description": parsed["style_description"],
        }

    async def validate_style(state: StyleExtractionState) -> dict[str, Any]:
        return {
            "style_validation_errors": _validate_style_description(
                state.get("style_description", ""),
                state.get("style_name", ""),
                state.get("description", ""),
            )
        }

    async def repair_style(state: StyleExtractionState) -> dict[str, Any]:
        repair_prompt = (
            "你需要修复一份 PPT 视觉风格模板。只输出修复后的完整 Markdown，必须包含 frontmatter，"
            "不要使用代码块。\n\n"
            f"校验问题：\n- " + "\n- ".join(state.get("style_validation_errors", [])) + "\n\n"
            f"资产盘点：\n{state.get('asset_inventory', '')}\n\n"
            f"页面布局盘点：\n{state.get('layout_inventory', '')}\n\n"
            f"原模板：\n{state.get('raw_style_output', '')}"
        )
        raw_style_output = await _invoke_text(llm, repair_prompt, "请修复风格模板。")
        parsed = parse_frontmatter(raw_style_output)
        style_name = parsed["name"] or state.get("style_name", "未命名风格")
        style_name_en = resolve_style_name_en(parsed["name_en"], style_name)
        return {
            "raw_style_output": raw_style_output,
            "style_name": style_name,
            "style_name_en": style_name_en,
            "description": parsed["description"] or state.get("description", ""),
            "style_description": parsed["style_description"],
            "style_repair_attempts": state.get("style_repair_attempts", 0) + 1,
        }

    async def generate_preview(state: StyleExtractionState) -> dict[str, Any]:
        if on_before_preview:
            await on_before_preview(state)
        system_prompt = prompt_manager.build_preview_html_prompt(
            state.get("style_description", ""),
            state.get("resource_base_url", ""),
            state.get("resource_manifest", []),
        )
        raw_preview_html = await _invoke_text(
            llm,
            system_prompt,
            "请严格按照以上风格模版，生成完整的预览 HTML 文件。",
        )
        return {
            "raw_preview_html": raw_preview_html,
            "preview_html": strip_code_fence(raw_preview_html),
        }

    async def validate_preview(state: StyleExtractionState) -> dict[str, Any]:
        return {
            "preview_validation_errors": _validate_preview_html(
                state.get("preview_html", ""),
                state.get("style_description", ""),
            )
        }

    async def repair_preview(state: StyleExtractionState) -> dict[str, Any]:
        repair_prompt = (
            "你需要修复 PPT 风格预览 HTML。只输出完整 HTML，不要使用代码块。"
            "保持现有视觉风格，但必须满足所有校验问题。\n\n"
            f"校验问题：\n- " + "\n- ".join(state.get("preview_validation_errors", [])) + "\n\n"
            f"风格模板：\n{state.get('style_description', '')}\n\n"
            f"资源清单：\n{state.get('resource_manifest', [])}\n\n"
            f"原 HTML：\n{state.get('preview_html', '')}"
        )
        raw_preview_html = await _invoke_text(llm, repair_prompt, "请修复预览 HTML。")
        return {
            "raw_preview_html": raw_preview_html,
            "preview_html": strip_code_fence(raw_preview_html),
            "preview_repair_attempts": state.get("preview_repair_attempts", 0) + 1,
        }

    def route_style_validation(state: StyleExtractionState) -> str:
        if state.get("style_validation_errors") and state.get("style_repair_attempts", 0) < 1:
            return "repair_style"
        return "generate_preview"

    def route_preview_validation(state: StyleExtractionState) -> str:
        if state.get("preview_validation_errors") and state.get("preview_repair_attempts", 0) < 1:
            return "repair_preview"
        return END

    graph = StateGraph(StyleExtractionState)
    graph.add_node("asset_inventory", asset_inventory)
    graph.add_node("layout_inventory", layout_inventory)
    graph.add_node("generate_style", generate_style)
    graph.add_node("validate_style", validate_style)
    graph.add_node("repair_style", repair_style)
    graph.add_node("generate_preview", generate_preview)
    graph.add_node("validate_preview", validate_preview)
    graph.add_node("repair_preview", repair_preview)
    graph.add_edge(START, "asset_inventory")
    graph.add_edge("asset_inventory", "layout_inventory")
    graph.add_edge("layout_inventory", "generate_style")
    graph.add_edge("generate_style", "validate_style")
    graph.add_conditional_edges("validate_style", route_style_validation)
    graph.add_edge("repair_style", "validate_style")
    graph.add_edge("generate_preview", "validate_preview")
    graph.add_conditional_edges("validate_preview", route_preview_validation)
    graph.add_edge("repair_preview", "validate_preview")
    return graph.compile()
