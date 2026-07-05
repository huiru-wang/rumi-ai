"""File-backed invite code registry with hot reload."""

from __future__ import annotations

import json
import logging
import os
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class InviteRecord:
    code: str
    user_id: str
    nickname: str
    enabled: bool = True
    expires_at: str | None = None


class InviteRegistry:
    """Load invite mappings from a local JSON file.

    The file is re-read on each lookup. If a hot-updated file is temporarily
    invalid, the last valid mapping remains active.
    """

    def __init__(self, file_path: str):
        self.file_path = Path(file_path)
        self._records_by_code: dict[str, InviteRecord] = {}
        self._valid_user_ids: set[str] = set()
        self._loaded_once = False

    @classmethod
    def from_env(cls) -> "InviteRegistry":
        default_path = Path(os.getenv("DATA_DIR", "./data")) / "invites.json"
        return cls(os.getenv("INVITE_CODES_FILE", str(default_path)))

    def claim(self, code: str) -> InviteRecord | None:
        self._reload_if_possible()
        normalized_code = code.strip()
        if not normalized_code:
            return None
        record = self._records_by_code.get(normalized_code)
        if not record or not record.enabled or self._is_expired(record.expires_at):
            return None
        return record

    def is_valid_user_id(self, user_id: str) -> bool:
        self._reload_if_possible()
        return user_id in self._valid_user_ids

    def _reload_if_possible(self):
        try:
            records = self._read_records()
        except Exception as exc:
            if not self._loaded_once:
                logger.warning("[InviteRegistry] failed to load invite file %s: %s", self.file_path, exc)
            else:
                logger.warning(
                    "[InviteRegistry] keeping previous invites; reload failed for %s: %s",
                    self.file_path,
                    exc,
                )
            return

        self._records_by_code = {record.code: record for record in records}
        self._valid_user_ids = {
            record.user_id
            for record in records
            if record.enabled and not self._is_expired(record.expires_at)
        }
        self._loaded_once = True

    def _read_records(self) -> list[InviteRecord]:
        with self.file_path.open("r", encoding="utf-8") as f:
            data = json.load(f)
        raw_invites = data.get("invites") if isinstance(data, dict) else None
        if not isinstance(raw_invites, list):
            raise ValueError("invite file must contain an invites list")

        records: list[InviteRecord] = []
        seen_codes: set[str] = set()
        for item in raw_invites:
            record = self._parse_record(item)
            if record.code in seen_codes:
                raise ValueError(f"duplicate invite code: {record.code}")
            seen_codes.add(record.code)
            records.append(record)
        return records

    def _parse_record(self, item: Any) -> InviteRecord:
        if not isinstance(item, dict):
            raise ValueError("invite record must be an object")
        code = str(item.get("code", "")).strip()
        user_id = str(item.get("user_id", "")).strip()
        nickname = str(item.get("nickname", "")).strip()
        expires_at = item.get("expires_at")
        if not code:
            raise ValueError("invite code is required")
        uuid.UUID(user_id)
        if not nickname:
            nickname = code
        if expires_at is not None:
            expires_at = str(expires_at).strip() or None
            if expires_at:
                self._parse_datetime(expires_at)
        return InviteRecord(
            code=code,
            user_id=user_id,
            nickname=nickname,
            enabled=bool(item.get("enabled", True)),
            expires_at=expires_at,
        )

    def _is_expired(self, expires_at: str | None) -> bool:
        if not expires_at:
            return False
        return self._parse_datetime(expires_at) <= datetime.now(timezone.utc)

    def _parse_datetime(self, value: str) -> datetime:
        normalized = value.replace("Z", "+00:00")
        parsed = datetime.fromisoformat(normalized)
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed.astimezone(timezone.utc)
