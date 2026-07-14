"""Small, stateless administrator session authentication."""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
from collections.abc import Callable
from datetime import datetime, timedelta, timezone


class AdminAuthError(Exception):
    pass


class AdminAuth:
    def __init__(
        self,
        username: str,
        password: str,
        secret: str,
        *,
        ttl: timedelta | None = None,
        now: Callable[[], datetime] | None = None,
    ):
        self.username = username
        self.password = password
        self.secret = secret
        self.ttl = ttl or timedelta(hours=12)
        self.now = now or (lambda: datetime.now(timezone.utc))

    @classmethod
    def from_env(cls) -> "AdminAuth":
        return cls(
            os.getenv("ADMIN_USERNAME", ""),
            os.getenv("ADMIN_PASSWORD", ""),
            os.getenv("ADMIN_SESSION_SECRET", ""),
        )

    def login(self, username: str, password: str) -> str:
        if not self.username or not self.password or not self.secret:
            raise AdminAuthError("administrator login is not configured")
        if not hmac.compare_digest(username, self.username) or not hmac.compare_digest(
            password, self.password
        ):
            raise AdminAuthError("invalid administrator credentials")
        expires_at = int((self.now() + self.ttl).timestamp())
        payload = self._encode({"sub": self.username, "exp": expires_at})
        signature = hmac.new(
            self.secret.encode("utf-8"), payload.encode("ascii"), hashlib.sha256
        ).hexdigest()
        return f"{payload}.{signature}"

    def verify(self, token: str) -> str:
        if not self.secret:
            raise AdminAuthError("administrator login is not configured")
        try:
            payload, signature = token.split(".", 1)
            expected = hmac.new(
                self.secret.encode("utf-8"), payload.encode("ascii"), hashlib.sha256
            ).hexdigest()
            if not hmac.compare_digest(signature, expected):
                raise AdminAuthError("invalid administrator session")
            data = json.loads(self._decode(payload))
            username = str(data["sub"])
            expires_at = int(data["exp"])
        except AdminAuthError:
            raise
        except (KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
            raise AdminAuthError("invalid administrator session") from exc
        if username != self.username or expires_at <= int(self.now().timestamp()):
            raise AdminAuthError("administrator session expired")
        return username

    @staticmethod
    def _encode(data: dict) -> str:
        raw = json.dumps(data, separators=(",", ":")).encode("utf-8")
        return base64.urlsafe_b64encode(raw).rstrip(b"=").decode("ascii")

    @staticmethod
    def _decode(value: str) -> str:
        padding = "=" * (-len(value) % 4)
        return base64.urlsafe_b64decode(value + padding).decode("utf-8")
