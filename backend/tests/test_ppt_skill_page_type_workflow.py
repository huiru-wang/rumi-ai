from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
PPT_SKILL = ROOT / "backend" / "skills" / "ppt" / "SKILL.md"
PAGE_LAYOUT_CONTRACT = (
    ROOT / "backend" / "skills" / "ppt" / "references" / "page-layout-contract.md"
)
OUTLINE_PLANNING_CONTRACT = (
    ROOT / "backend" / "skills" / "ppt" / "references" / "outline-planning-contract.md"
)
MAGAZINE_INK = (
    ROOT / "backend" / "src" / "storage" / "seed_data" / "ppt_styles" / "magazine-ink.md"
)
SYSTEM_STYLE_DIR = ROOT / "backend" / "src" / "storage" / "seed_data" / "ppt_styles"
STYLE_EXTRACT_PROMPT = ROOT / "backend" / "src" / "managers" / "prompts" / "style_extract_prompt.md"
GENERATE_COVER_PROMPT = (
    ROOT / "backend" / "src" / "managers" / "prompts" / "generate_cover_html_prompt.md"
)


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_ppt_skill_uses_direct_five_phase_workflow() -> None:
    text = _read(PPT_SKILL)

    for phase in range(1, 6):
        assert f"## Phase {phase}:" in text

    assert "## Phase 1.5:" not in text
    assert "## Phase 1.6:" not in text
    assert "## Phase 2.5:" not in text
    assert "## Phase 3.5:" not in text


def test_ppt_skill_removes_content_density_form_and_uses_page_types() -> None:
    text = _read(PPT_SKILL)

    assert "Question 5 — Content Density" not in text
    assert "内容密度：" not in text
    assert '"density"' not in text
    assert '"page_type"' in text
    assert '"layout_variant"' in text
    assert '"content_intent"' in text
    assert "cover -> agenda -> section -> content -> closing" in text

    for page_type in ("cover", "agenda", "section", "content", "closing"):
        assert page_type in text


def test_ppt_skill_extracts_page_layout_rules_to_references() -> None:
    skill_text = _read(PPT_SKILL)
    page_contract = _read(PAGE_LAYOUT_CONTRACT)
    outline_contract = _read(OUTLINE_PLANNING_CONTRACT)

    assert "references/page-layout-contract.md" in skill_text
    assert "references/outline-planning-contract.md" in skill_text
    assert "用户可见大纲必须使用中文页面类型" in page_contract
    assert "page_layouts:" in page_contract
    assert "section_policy:" in page_contract
    assert "先识别内容分组" in outline_contract
    assert "禁止只给一个并列主题插入章节页" in outline_contract


def test_user_visible_outline_uses_chinese_page_types() -> None:
    text = _read(PPT_SKILL)

    assert "| 1 | 封面页 | 杂志封面英雄页 |" in text
    assert "| 2 | 内容页 | 左文右图型 |" in text
    assert "| 1 | cover |" not in text
    assert "| 2 | content |" not in text


def test_style_template_is_read_before_outline_confirmation() -> None:
    text = _read(PPT_SKILL)

    style_index = text.index("get_style_template")
    outline_index = text.index("## Phase 3: Outline Confirmation")

    assert style_index < outline_index
    assert "Phase 2 material inventory and style layout map" in text


def test_magazine_ink_declares_normalized_page_layouts() -> None:
    text = _read(MAGAZINE_INK)

    assert "page_layouts:" in text
    assert "cover:" in text
    assert "agenda:" in text
    assert "section:" in text
    assert "content:" in text
    assert "closing:" in text
    assert "enabled: false" in text

    for variant in (
        "cover.editorial_hero",
        "section.chapter_divider",
        "content.split_text_visual",
        "content.statement_quote",
        "closing.hero_end",
    ):
        assert variant in text

    assert "section_policy:" in text
    assert "each section introduces at least 2 following content slides" in text
    assert "do not create a section page for one peer topic" in text


def test_all_system_styles_declare_normalized_page_layouts() -> None:
    for path in sorted(SYSTEM_STYLE_DIR.glob("*.md")):
        text = _read(path)

        assert "page_layouts:" in text, path.name
        assert "section_policy:" in text, path.name

        for page_type, display_name in (
            ("cover:", "display_name: 封面页"),
            ("agenda:", "display_name: 目录页"),
            ("section:", "display_name: 章节页"),
            ("content:", "display_name: 内容页"),
            ("closing:", "display_name: 封底页"),
        ):
            assert page_type in text, path.name
            assert display_name in text, path.name

        assert "enabled: false" in text or "enabled: true" in text, path.name
        assert "do not create a section page for one peer topic" in text, path.name


def test_style_extraction_prompt_requires_normalized_layout_contract() -> None:
    text = _read(STYLE_EXTRACT_PROMPT)

    assert "page_layouts" in text
    assert "section_policy" in text
    assert "display_name" in text
    assert "封面页 / 目录页 / 章节页 / 内容页 / 封底页" in text


def test_prompt_manager_appends_shared_page_layout_contract() -> None:
    from src.managers.prompt_manager import PromptManager

    prompt = PromptManager().build_style_description_prompt("## mock pptx report")

    assert "## 共享页面布局契约" in prompt
    assert "page_layouts:" in prompt
    assert "section_policy:" in prompt
    assert "用户可见大纲必须使用中文页面类型" in prompt


def test_cover_preview_prompt_prefers_normalized_cover_layout() -> None:
    text = _read(GENERATE_COVER_PROMPT)

    assert "page_layouts.cover" in text
    assert "cover.*" in text
