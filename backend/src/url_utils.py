"""Helpers for building frontend-safe public API URLs."""

import os
from urllib.parse import quote


def get_public_api_base() -> str:
    """Return the externally reachable FastAPI base URL."""
    return os.getenv("PUBLIC_API_BASE", "http://localhost:8000").rstrip("/")


def build_share_ppt_url(token: str) -> str:
    """Build a share PPT API path without assuming the public API origin."""
    return f"/api/shares/{quote(token, safe='')}/ppt"


def build_share_audio_url(token: str, slide_number: int) -> str:
    """Build a share narration audio API path without assuming the public API origin."""
    return f"/api/shares/{quote(token, safe='')}/audio/{slide_number}"


def build_style_resource_url(style_id: str, filename: str) -> str:
    """Build a public proxy URL for a saved custom style resource."""
    return (
        f"{get_public_api_base()}/api/ppt-styles/"
        f"{quote(style_id, safe='')}/resource/{quote(filename, safe='')}"
    )


def build_style_extraction_resource_url(task_id: str, filename: str) -> str:
    """Build a public proxy URL for a style extraction task resource."""
    return (
        f"{get_public_api_base()}/api/tasks/"
        f"{quote(task_id, safe='')}/style-resource/{quote(filename, safe='')}"
    )


def build_document_asset_url(doc_id: str, filename: str) -> str:
    """Build a frontend-safe proxy path for a document-derived asset."""
    return (
        f"/api/documents/"
        f"{quote(doc_id, safe='')}/asset/{quote(filename, safe='')}"
    )
