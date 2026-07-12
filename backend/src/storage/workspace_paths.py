"""Workspace-scoped runtime work directories."""

from __future__ import annotations

import os
import re
import shutil
from pathlib import Path

_SAFE_SEGMENT_PATTERN = re.compile(r"[^a-zA-Z0-9_.-]+")


def safe_segment(value: str) -> str:
    """Return a filesystem-safe path segment for app-generated IDs."""
    segment = _SAFE_SEGMENT_PATTERN.sub("_", str(value).strip()).strip("._")
    return segment or "unknown"


def safe_filename(value: str, fallback: str = "file") -> str:
    """Return a filesystem-safe filename while preserving the suffix when possible."""
    original = Path(str(value)).name
    stem = safe_segment(Path(original).stem)
    if stem == "unknown":
        stem = safe_segment(fallback)
    suffix = _SAFE_SEGMENT_PATTERN.sub("", Path(original).suffix)
    return f"{stem}{suffix}" if suffix else stem


def data_root() -> Path:
    """Return the configured project data root."""
    return Path(os.getenv("DATA_DIR", "./data")).expanduser().resolve()


def workspace_work_dir(workspace_id: str) -> Path:
    """Return the root work directory for a workspace."""
    return data_root() / "workspace_work" / safe_segment(workspace_id)


def doc_parse_dir(workspace_id: str, doc_id: str) -> Path:
    """Return the document parsing work directory."""
    return workspace_work_dir(workspace_id) / "doc_parse" / safe_segment(doc_id)


def style_extract_dir(workspace_id: str, task_id: str) -> Path:
    """Return the style extraction work directory."""
    return workspace_work_dir(workspace_id) / "style_extract" / safe_segment(task_id)


def reset_dir(path: Path) -> Path:
    """Create an empty directory at path."""
    shutil.rmtree(path, ignore_errors=True)
    path.mkdir(parents=True, exist_ok=True)
    return path


def delete_workspace_work_dir(workspace_id: str) -> None:
    """Delete all runtime work files for a workspace."""
    shutil.rmtree(workspace_work_dir(workspace_id), ignore_errors=True)


def delete_style_extract_dir(workspace_id: str, task_id: str) -> None:
    """Delete runtime work files for one style extraction task."""
    shutil.rmtree(style_extract_dir(workspace_id, task_id), ignore_errors=True)
