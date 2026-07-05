import shutil
import uuid
from pathlib import Path

from src.managers.doc_manager import DocManager


def test_save_dev_parse_artifacts_writes_json_and_markdown(monkeypatch):
    monkeypatch.setenv("APP_ENV", "dev")
    doc_id = f"test-{uuid.uuid4().hex}"
    manager = object.__new__(DocManager)

    manager._save_dev_parse_artifacts(
        doc_id=doc_id,
        filename="demo.pdf",
        parsed_json_content='{"title":"demo"}',
        markdown_content="# Demo\n\ncontent",
    )

    repo_root = Path(__file__).resolve().parents[2]
    output_dir = repo_root / "tmp" / "doc_parse" / doc_id
    try:
        assert (output_dir / "demo.parsed.json").read_text(encoding="utf-8") == '{"title":"demo"}'
        assert (output_dir / "demo.md").read_text(encoding="utf-8") == "# Demo\n\ncontent"
    finally:
        shutil.rmtree(output_dir, ignore_errors=True)


def test_save_dev_parse_artifacts_skips_prod(monkeypatch):
    monkeypatch.setenv("APP_ENV", "prod")
    doc_id = f"test-{uuid.uuid4().hex}"
    manager = object.__new__(DocManager)

    manager._save_dev_parse_artifacts(
        doc_id=doc_id,
        filename="demo.pdf",
        parsed_json_content="{}",
        markdown_content="content",
    )

    repo_root = Path(__file__).resolve().parents[2]
    output_dir = repo_root / "tmp" / "doc_parse" / doc_id
    assert not output_dir.exists()
