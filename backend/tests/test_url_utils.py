from src.url_utils import build_document_asset_url


def test_document_asset_url_is_origin_relative(monkeypatch):
    monkeypatch.setenv("PUBLIC_API_BASE", "http://localhost:8000")

    url = build_document_asset_url("doc 1", "image 1.png")

    assert url == "/api/documents/doc%201/asset/image%201.png"
