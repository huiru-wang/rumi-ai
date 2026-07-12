"""Pure parsing and validation helpers for PPT style extraction."""

from __future__ import annotations

import hashlib
import re


PAGE_TYPES = ("cover", "agenda", "section", "content", "closing")


def parse_frontmatter(llm_output: str) -> dict[str, str]:
    output = llm_output.strip()
    if output.startswith("---"):
        rest = output[3:].lstrip("\n")
        end_idx = rest.find("\n---")
        if end_idx != -1:
            values = {"name": "", "name_en": "", "description": ""}
            for line in rest[:end_idx].splitlines():
                key, separator, value = line.partition(":")
                if separator and key.strip() in values:
                    values[key.strip()] = value.strip().strip("\"'")
            return {**values, "style_description": rest[end_idx + 4 :].lstrip("\n").strip()}
    return {"name": "", "name_en": "", "description": "", "style_description": output}


def resolve_style_name_en(name_en: str, name: str) -> str:
    normalized = re.sub(r"[^a-zA-Z0-9\s-]", "", name_en).strip().lower()
    normalized = re.sub(r"\s+", "-", normalized)
    if normalized and re.search(r"[a-z]", normalized):
        return normalized
    return f"style-{hashlib.md5((name or 'unnamed').encode()).hexdigest()[:6]}"


def validate_style_description(style_description: str, style_name: str, description: str) -> list[str]:
    errors: list[str] = []
    if not style_name or style_name == "未命名风格":
        errors.append("缺少可用的中文风格名")
    if not description:
        errors.append("frontmatter 缺少 description")
    if "page_layouts:" not in style_description:
        errors.append("Layout Grammar 缺少标准化 page_layouts")
    if "section_policy:" not in style_description:
        errors.append("缺少 section_policy")
    for page_type, display_name in zip(PAGE_TYPES, ("封面页", "目录页", "章节页", "内容页", "封底页")):
        if not re.search(rf"^\s{{2}}{page_type}:\s*$", style_description, re.M):
            errors.append(f"page_layouts 缺少 {page_type}")
        if f"display_name: {display_name}" not in style_description:
            errors.append(f"{page_type} 缺少中文 display_name")
    return errors


def extract_enabled_page_types(style_description: str) -> list[str]:
    enabled: list[str] = []
    lines = style_description.splitlines()
    for page_type in PAGE_TYPES:
        start = next((i for i, line in enumerate(lines) if re.match(rf"^\s{{2}}{page_type}:\s*$", line)), None)
        if start is None:
            continue
        block = []
        for line in lines[start + 1 :]:
            if re.match(r"^\s{2}(cover|agenda|section|content|closing):\s*$", line):
                break
            block.append(line)
        if any(re.match(r"^\s+enabled:\s*true\s*$", line) for line in block):
            enabled.append(page_type)
    return enabled or ["cover", "content"]


def validate_preview_html(preview_html: str, style_description: str) -> list[str]:
    errors: list[str] = []
    lowered = preview_html.lower()
    if "<!doctype html>" not in lowered[:200]:
        errors.append("预览 HTML 缺少 <!DOCTYPE html>")
    for forbidden in ("contenteditable", "localstorage", "inlineeditor"):
        if forbidden in lowered:
            errors.append(f"预览 HTML 不能包含 {forbidden}")
    enabled_types = extract_enabled_page_types(style_description)
    slides = re.findall(r"<section\b[^>]*class=[\"'][^\"']*\bslide\b[^>]*>", preview_html, re.I)
    if len(slides) < len(enabled_types):
        errors.append(f"预览页数不足，应覆盖启用页面类型：{', '.join(enabled_types)}")
    for page_type in enabled_types:
        if not re.search(rf"data-page-type=[\"']{page_type}[\"']", preview_html):
            errors.append(f"预览 HTML 未覆盖页面类型 {page_type}")
    if slides and any("data-layout=" not in slide.lower() for slide in slides):
        errors.append("每个预览页面都必须包含 data-layout")
    if 'data-preview-mode="readonly"' not in lowered and "data-preview-mode='readonly'" not in lowered:
        errors.append("预览 HTML 缺少只读预览标记")
    return errors
