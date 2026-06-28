import json

from src.api.routes import _resource_replacements_from_manifest
from src.tools.get_style_template import _build_template_text
from src.url_utils import build_style_resource_url


def test_style_template_rewrites_resource_urls_to_public_api_proxy(monkeypatch):
    monkeypatch.setenv("PUBLIC_API_BASE", "https://api.example.com")
    record = {
        "id": "style-123",
        "name": "Custom",
        "name_en": "custom",
        "description": "desc",
        "style_description": "Use the background image.",
        "resource_manifest": json.dumps(
            [
                {
                    "filename": "Slide-1-image-1.png",
                    "url": "https://bucket.oss-cn-hangzhou.aliyuncs.com/user/u/style/style-123/resource/Slide-1-image-1.png",
                    "description": {"usage_notes": "封面背景"},
                }
            ],
            ensure_ascii=False,
        ),
    }

    text = _build_template_text(record)

    assert "https://api.example.com/api/ppt-styles/style-123/resource/Slide-1-image-1.png" in text
    assert "aliyuncs.com" not in text
    assert "user/u/style" not in text


def test_preview_resource_replacements_use_public_api_proxy(monkeypatch):
    monkeypatch.setenv("PUBLIC_API_BASE", "https://api.example.com/")
    manifest = [
        {
            "filename": "Slide 1.png",
            "url": "https://bucket.oss-cn-hangzhou.aliyuncs.com/user/u/style/style-123/resource/Slide%201.png",
        }
    ]

    replacements = _resource_replacements_from_manifest(
        manifest,
        lambda filename: build_style_resource_url("style-123", filename),
    )

    assert replacements == [
        (
            "https://bucket.oss-cn-hangzhou.aliyuncs.com/user/u/style/style-123/resource/Slide%201.png",
            "https://api.example.com/api/ppt-styles/style-123/resource/Slide%201.png",
        )
    ]
