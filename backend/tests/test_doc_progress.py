from src.managers.doc_manager import build_document_progress, merge_progress_percent


def test_parsing_progress_uses_global_stage_range():
    progress = build_document_progress(
        "parsing",
        message="正在解析 PDF 页面",
        current=5,
        total=10,
    )

    assert progress["percent"] == 25


def test_late_stages_use_global_percent_ranges():
    assert build_document_progress("uploaded")["percent"] == 5
    assert build_document_progress("parsed")["percent"] == 60
    assert build_document_progress("indexing")["percent"] == 70
    assert build_document_progress("summarizing")["percent"] == 88
    assert build_document_progress("ready")["percent"] == 100


def test_progress_merge_never_moves_backward():
    progress = build_document_progress("parsing", percent=20)

    merged = merge_progress_percent(progress, {"percent": 56})

    assert merged["percent"] == 56
