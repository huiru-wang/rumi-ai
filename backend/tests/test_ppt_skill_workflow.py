from pathlib import Path


PPT_SKILL = Path(__file__).resolve().parents[1] / "skills" / "ppt" / "SKILL.md"


def _skill_text() -> str:
    return PPT_SKILL.read_text(encoding="utf-8")


def test_ppt_skill_collects_full_content_before_outline():
    text = _skill_text()

    assert "Question 5 — Content Density" in text
    assert "Phase 1.5: Full Content & Asset Gathering" in text
    assert "generate the outline" in text
    assert "Content & Asset Inventory" in text
    assert "The goal is to collect enough material for the whole presentation" in text


def test_ppt_skill_plans_slide_briefs_from_collected_materials():
    text = _skill_text()

    assert "Phase 2.5: Slide Design Briefs" in text
    assert "| # | Slide Goal | Material Used | Layout | Image/Chart Handling | Density Handling |" in text
    assert "Do not add another user confirmation gate" in text


def test_ppt_skill_keeps_retrieval_flexible_without_secondary_checks():
    text = _skill_text()

    assert "Do not prescribe a fixed number of `rag_search` calls" in text
    assert "Do not perform a per-slide RAG verification pass" in text
    assert "Do not add a separate second-pass quality-check phase" in text
    assert "Phase 3.5" not in text
