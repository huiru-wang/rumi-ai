from src.tools.rag_search import _format_ref_marker, _format_result


def test_format_ref_marker_uses_filename_page_and_two_level_titles():
    marker = _format_ref_marker(
        {
            "filename": "年度报告.pdf",
            "chapter_title": "经营分析",
            "section_title": "现金流情况",
            "page_start": 18,
            "page_end": 18,
        }
    )

    assert marker == "[ref:年度报告.pdf|第18页|经营分析|现金流情况]"


def test_format_ref_marker_keeps_page_placeholder_when_page_missing():
    marker = _format_ref_marker(
        {
            "filename": "产品需求文档.docx",
            "chapter_title": "用户管理",
            "section_title": "权限模型",
            "page_start": 0,
            "page_end": 0,
        }
    )

    assert marker == "[ref:产品需求文档.docx|-|用户管理|权限模型]"


def test_format_result_includes_markdown_image_for_image_chunk(monkeypatch):
    monkeypatch.setenv("PUBLIC_API_BASE", "https://api.example.com")

    text = _format_result(
        0,
        {
            "filename": "demo.docx",
            "text": "图片：图1 架构图\n图片说明：图片展示系统架构。",
            "doc_id": "doc-123",
            "block_type": "image",
            "caption": "图1 架构图",
            "asset_path": "user/u/workspace/ws/docs/demo_assets/image_001.png",
            "section_title": "系统设计",
            "page_start": 2,
            "page_end": 2,
            "chunk_index": 0,
        },
    )

    assert "来源索引：[ref:demo.docx|第2页|系统设计]" in text
    assert "![图1 架构图]" in text
    assert "https://api.example.com/api/documents/doc-123/asset/image_001.png" in text
    assert "可直接用于最终回答的图片 Markdown" in text
