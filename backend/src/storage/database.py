import random
import secrets
import uuid
from datetime import datetime, timedelta, timezone
import json
from typing import Any

import aiosqlite

from src.storage.seeds import _BUILTIN_PPT_STYLES, get_default_voice_info


class Database:
    def __init__(self, db_path: str):
        self.db_path = db_path
        self.connection: aiosqlite.Connection | None = None

    async def initialize(self):
        if self.connection:
            return
        self.connection = await aiosqlite.connect(self.db_path)
        self.connection.row_factory = aiosqlite.Row
        await self._create_tables()

    async def ensure_initialized(self):
        if not self.connection:
            await self.initialize()

    async def _create_tables(self):
        await self.connection.executescript("""
            CREATE TABLE IF NOT EXISTS workspace (
                id TEXT PRIMARY KEY,
                user_id TEXT NOT NULL,
                name TEXT NOT NULL,
                thread_id TEXT,
                created_at TEXT DEFAULT (datetime('now', 'localtime'))
            );
            CREATE TABLE IF NOT EXISTS document (
                id TEXT PRIMARY KEY,
                workspace_id TEXT NOT NULL REFERENCES workspace(id) ON DELETE CASCADE,
                filename TEXT NOT NULL,
                file_type TEXT,
                summary TEXT,
                storage_path TEXT,
                status TEXT DEFAULT 'uploaded',
                error_message TEXT,
                progress_data TEXT,
                created_at TEXT DEFAULT (datetime('now', 'localtime')),
                updated_at TEXT DEFAULT (datetime('now', 'localtime'))
            );
            CREATE TABLE IF NOT EXISTS task (
                id TEXT PRIMARY KEY,
                workspace_id TEXT NOT NULL REFERENCES workspace(id) ON DELETE CASCADE,
                type TEXT NOT NULL,
                title TEXT,
                status TEXT DEFAULT 'generating',
                result_data TEXT,
                created_at TEXT DEFAULT (datetime('now', 'localtime')),
                updated_at TEXT DEFAULT (datetime('now', 'localtime'))
            );
            CREATE TABLE IF NOT EXISTS message (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                thread_id TEXT NOT NULL,
                workspace_id TEXT,
                run_id TEXT,
                message_id TEXT NOT NULL,
                role TEXT NOT NULL,
                type TEXT NOT NULL,
                content TEXT NOT NULL,
                tool_calls TEXT,
                tool_call_id TEXT,
                name TEXT,
                additional_kwargs TEXT,
                response_metadata TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                UNIQUE(thread_id, message_id, role)
            );
            CREATE TABLE IF NOT EXISTS ppt_style (
                id TEXT PRIMARY KEY,
                user_id TEXT NOT NULL,
                category TEXT NOT NULL,
                name TEXT NOT NULL,
                name_en TEXT DEFAULT '',
                description TEXT DEFAULT '',
                style_description TEXT DEFAULT '',
                resource_manifest TEXT DEFAULT '[]',
                preview_path TEXT DEFAULT '',
                created_at TEXT DEFAULT (datetime('now', 'localtime'))
            );
            CREATE TABLE IF NOT EXISTS share_link (
                token TEXT PRIMARY KEY,
                task_id TEXT NOT NULL,
                workspace_id TEXT NOT NULL,
                type TEXT NOT NULL,
                created_at TEXT DEFAULT (datetime('now', 'localtime')),
                revoked_at TEXT,
                revoked_reason TEXT
            );
            CREATE TABLE IF NOT EXISTS invite_code (
                id TEXT PRIMARY KEY,
                code TEXT NOT NULL UNIQUE,
                user_id TEXT NOT NULL UNIQUE,
                nickname TEXT NOT NULL,
                enabled INTEGER NOT NULL DEFAULT 1,
                expires_at TEXT,
                claimed_at TEXT,
                last_claimed_at TEXT,
                claim_count INTEGER NOT NULL DEFAULT 0,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS system_setting (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS app_user (
                user_id TEXT PRIMARY KEY,
                source TEXT NOT NULL,
                nickname TEXT NOT NULL,
                created_at TEXT NOT NULL,
                last_seen_at TEXT NOT NULL
            );
            CREATE INDEX IF NOT EXISTS idx_ppt_style_user ON ppt_style(user_id);
            CREATE INDEX IF NOT EXISTS idx_share_link_task_active
                ON share_link(task_id, revoked_at);
            CREATE INDEX IF NOT EXISTS idx_message_thread_id_id
                ON message(thread_id, id DESC);
            CREATE INDEX IF NOT EXISTS idx_invite_claimed_at
                ON invite_code(claimed_at);
            CREATE INDEX IF NOT EXISTS idx_app_user_source
                ON app_user(source);
            PRAGMA foreign_keys = ON;
        """)
        now = datetime.now(timezone.utc).isoformat()
        await self.connection.execute(
            "INSERT OR IGNORE INTO system_setting (key, value, updated_at) VALUES ('invite_required', 'true', ?)",
            (now,),
        )
        await self._migrate_tables()
        await self.connection.execute(
            """
            INSERT OR IGNORE INTO app_user
                (user_id, source, nickname, created_at, last_seen_at)
            SELECT
                i.user_id,
                'invite',
                i.nickname,
                COALESCE(i.claimed_at, i.created_at),
                COALESCE(i.last_claimed_at, i.claimed_at, i.created_at)
            FROM invite_code i
            WHERE i.claimed_at IS NOT NULL
               OR EXISTS (
                    SELECT 1 FROM workspace w WHERE w.user_id = i.user_id
               )
            """
        )
        await self.connection.commit()

    async def _migrate_tables(self):
        cursor = await self.connection.execute("PRAGMA table_info(document)")
        columns = {row["name"] for row in await cursor.fetchall()}
        if "error_message" not in columns:
            await self.connection.execute("ALTER TABLE document ADD COLUMN error_message TEXT")
        if "updated_at" not in columns:
            cursor = await self.connection.execute(
                "ALTER TABLE document ADD COLUMN updated_at TEXT DEFAULT (datetime('now', 'localtime'))"
            )
        if "content_hash" not in columns:
            await self.connection.execute(
                "ALTER TABLE document ADD COLUMN content_hash TEXT"
            )
            await self.connection.execute(
                "CREATE INDEX IF NOT EXISTS idx_document_hash ON document(workspace_id, content_hash)"
            )
        if "progress_data" not in columns:
            await self.connection.execute(
                "ALTER TABLE document ADD COLUMN progress_data TEXT"
            )

        # workspace: add ext_data column with default config
        cursor = await self.connection.execute("PRAGMA table_info(workspace)")
        ws_columns = {row["name"] for row in await cursor.fetchall()}
        if "ext_data" not in ws_columns:
            default_voice_info = get_default_voice_info("Cherry")
            default_ext = json.dumps(
                {"ppt_style": "sys-swiss-modern", "voice_info": default_voice_info},
                ensure_ascii=False,
            )
            await self.connection.execute(
                f"ALTER TABLE workspace ADD COLUMN ext_data TEXT DEFAULT '{default_ext}'"
            )
            # Backfill existing rows that have NULL ext_data
            await self.connection.execute(
                "UPDATE workspace SET ext_data = ? WHERE ext_data IS NULL",
                (default_ext,),
            )

        # Backfill voice_info for workspaces that have voice_id but no voice_info,
        # and migrate voice_id into voice_info.id
        cursor = await self.connection.execute("SELECT id, ext_data FROM workspace WHERE ext_data IS NOT NULL")
        for row in await cursor.fetchall():
            try:
                ext = json.loads(row["ext_data"]) if isinstance(row["ext_data"], str) else {}
            except (json.JSONDecodeError, TypeError):
                ext = {}
            changed = False
            # Migrate: old voice_id → voice_info with id
            if ext.get("voice_id") and not ext.get("voice_info"):
                vi = get_default_voice_info(ext["voice_id"])
                if vi:
                    ext["voice_info"] = vi
                    changed = True
            # Remove standalone voice_id (now inside voice_info.id)
            if "voice_id" in ext:
                del ext["voice_id"]
                changed = True

            if changed:
                await self.connection.execute(
                    "UPDATE workspace SET ext_data = ? WHERE id = ?",
                    (json.dumps(ext, ensure_ascii=False), row["id"]),
                )

        # task: add parent_task_id column
        cursor = await self.connection.execute("PRAGMA table_info(task)")
        task_columns = {row["name"] for row in await cursor.fetchall()}
        if "parent_task_id" not in task_columns:
            await self.connection.execute(
                "ALTER TABLE task ADD COLUMN parent_task_id TEXT REFERENCES task(id) ON DELETE SET NULL"
            )
            await self.connection.execute(
                "CREATE INDEX IF NOT EXISTS idx_task_parent ON task(parent_task_id)"
            )

        cursor = await self.connection.execute("PRAGMA table_info(message)")
        message_columns = {row["name"] for row in await cursor.fetchall()}
        if message_columns:
            for column, ddl in {
                "workspace_id": "ALTER TABLE message ADD COLUMN workspace_id TEXT",
                "run_id": "ALTER TABLE message ADD COLUMN run_id TEXT",
                "tool_calls": "ALTER TABLE message ADD COLUMN tool_calls TEXT",
                "tool_call_id": "ALTER TABLE message ADD COLUMN tool_call_id TEXT",
                "name": "ALTER TABLE message ADD COLUMN name TEXT",
                "additional_kwargs": "ALTER TABLE message ADD COLUMN additional_kwargs TEXT",
                "response_metadata": "ALTER TABLE message ADD COLUMN response_metadata TEXT",
                "updated_at": "ALTER TABLE message ADD COLUMN updated_at TEXT",
            }.items():
                if column not in message_columns:
                    await self.connection.execute(ddl)
            await self.connection.execute(
                "CREATE INDEX IF NOT EXISTS idx_message_thread_run ON message(thread_id, run_id)"
            )
            await self.connection.execute(
                "CREATE INDEX IF NOT EXISTS idx_message_run ON message(run_id)"
            )

        # ppt_style: add resource_manifest column
        cursor = await self.connection.execute("PRAGMA table_info(ppt_style)")
        ppt_style_columns = {row["name"] for row in await cursor.fetchall()}
        if "resource_manifest" not in ppt_style_columns:
            await self.connection.execute(
                "ALTER TABLE ppt_style ADD COLUMN resource_manifest TEXT DEFAULT '[]'"
            )

        cursor = await self.connection.execute("PRAGMA table_info(share_link)")
        share_columns = {row["name"] for row in await cursor.fetchall()}
        if share_columns:
            if "revoked_reason" not in share_columns:
                await self.connection.execute(
                    "ALTER TABLE share_link ADD COLUMN revoked_reason TEXT"
                )
            await self.connection.execute(
                "CREATE INDEX IF NOT EXISTS idx_share_link_task_active ON share_link(task_id, revoked_at)"
            )

        # Clear old system styles and re-seed
        await self.connection.execute(
            "DELETE FROM ppt_style WHERE user_id = 'system'"
        )
        for style in _BUILTIN_PPT_STYLES:
            await self.connection.execute(
                """INSERT OR IGNORE INTO ppt_style
                   (id, user_id, category, name, name_en, description, style_description, preview_path)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    style["id"],
                    style["user_id"],
                    style["category"],
                    style["name"],
                    style["name_en"],
                    style["description"],
                    style["style_description"],
                    style["preview_path"],
                ),
            )

    async def close(self):
        if self.connection:
            await self.connection.close()

    # --- Workspace ---

    # --- Quota count helpers ---

    async def count_workspaces(self, user_id: str) -> int:
        """Count workspaces owned by a user."""
        await self.ensure_initialized()
        cursor = await self.connection.execute(
            "SELECT COUNT(*) as cnt FROM workspace WHERE user_id = ?",
            (user_id,),
        )
        row = await cursor.fetchone()
        return row["cnt"] if row else 0

    async def count_documents(self, workspace_id: str) -> int:
        """Count non-error documents in a workspace."""
        await self.ensure_initialized()
        cursor = await self.connection.execute(
            "SELECT COUNT(*) as cnt FROM document WHERE workspace_id = ? AND status != 'error'",
            (workspace_id,),
        )
        row = await cursor.fetchone()
        return row["cnt"] if row else 0

    async def count_tasks_by_type(self, workspace_id: str, task_type: str) -> int:
        """Count top-level tasks of a specific type in a workspace."""
        await self.ensure_initialized()
        cursor = await self.connection.execute(
            "SELECT COUNT(*) as cnt FROM task WHERE workspace_id = ? AND type = ? AND parent_task_id IS NULL",
            (workspace_id, task_type),
        )
        row = await cursor.fetchone()
        return row["cnt"] if row else 0

    async def count_child_tasks(self, parent_task_id: str, task_type: str) -> int:
        """Count child tasks of a specific type under a parent task."""
        await self.ensure_initialized()
        cursor = await self.connection.execute(
            "SELECT COUNT(*) as cnt FROM task WHERE parent_task_id = ? AND type = ?",
            (parent_task_id, task_type),
        )
        row = await cursor.fetchone()
        return row["cnt"] if row else 0

    async def count_custom_styles(self, user_id: str) -> int:
        """Count custom PPT styles owned by a user (excluding system styles)."""
        await self.ensure_initialized()
        cursor = await self.connection.execute(
            "SELECT COUNT(*) as cnt FROM ppt_style WHERE user_id = ? AND user_id != 'system'",
            (user_id,),
        )
        row = await cursor.fetchone()
        return row["cnt"] if row else 0

    # --- Invite codes ---

    async def get_invite_required(self) -> bool:
        await self.ensure_initialized()
        cursor = await self.connection.execute(
            "SELECT value FROM system_setting WHERE key = 'invite_required'"
        )
        row = await cursor.fetchone()
        return not row or row["value"].lower() == "true"

    async def set_invite_required(self, required: bool) -> bool:
        await self.ensure_initialized()
        now = datetime.now(timezone.utc).isoformat()
        await self.connection.execute(
            """
            INSERT INTO system_setting (key, value, updated_at)
            VALUES ('invite_required', ?, ?)
            ON CONFLICT(key) DO UPDATE SET value = excluded.value, updated_at = excluded.updated_at
            """,
            ("true" if required else "false", now),
        )
        await self.connection.commit()
        return required

    async def create_open_user(self) -> dict:
        await self.ensure_initialized()
        if await self.get_invite_required():
            raise PermissionError("open access is disabled")
        user_id = str(uuid.uuid4())
        nickname = f"访客 {user_id[:4].upper()}"
        now = datetime.now(timezone.utc).isoformat()
        await self.connection.execute(
            """
            INSERT INTO app_user (user_id, source, nickname, created_at, last_seen_at)
            VALUES (?, 'open', ?, ?, ?)
            """,
            (user_id, nickname, now, now),
        )
        await self.connection.commit()
        return {
            "user_id": user_id,
            "source": "open",
            "nickname": nickname,
            "created_at": now,
            "last_seen_at": now,
        }

    async def get_app_user(self, user_id: str) -> dict | None:
        await self.ensure_initialized()
        cursor = await self.connection.execute(
            "SELECT * FROM app_user WHERE user_id = ?", (user_id,)
        )
        row = await cursor.fetchone()
        return dict(row) if row else None

    async def is_access_user_allowed(self, user_id: str) -> bool:
        await self.ensure_initialized()
        invite_required = await self.get_invite_required()
        user = await self.get_app_user(user_id)
        if not invite_required and user:
            return True
        if not await self.is_valid_invited_user(user_id):
            return False
        if not user:
            cursor = await self.connection.execute(
                "SELECT nickname FROM invite_code WHERE user_id = ?", (user_id,)
            )
            invite = await cursor.fetchone()
            if not invite:
                return False
            now = datetime.now(timezone.utc).isoformat()
            await self.connection.execute(
                """
                INSERT OR IGNORE INTO app_user (user_id, source, nickname, created_at, last_seen_at)
                VALUES (?, 'invite', ?, ?, ?)
                """,
                (user_id, invite["nickname"], now, now),
            )
            await self.connection.commit()
        return True

    async def import_invites(self, records: list[dict]) -> int:
        """Idempotently import legacy file-backed invite records."""
        await self.ensure_initialized()
        now = datetime.now(timezone.utc).isoformat()
        imported = 0
        for record in records:
            code = str(record.get("code", "")).strip()
            user_id = str(record.get("user_id", "")).strip()
            if not code or not user_id:
                continue
            nickname = str(record.get("nickname", "")).strip() or code
            cursor = await self.connection.execute(
                """
                INSERT INTO invite_code (
                    id, code, user_id, nickname, enabled, expires_at, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT DO NOTHING
                """,
                (
                    str(uuid.uuid4()),
                    code,
                    user_id,
                    nickname,
                    int(bool(record.get("enabled", True))),
                    record.get("expires_at"),
                    now,
                    now,
                ),
            )
            imported += max(cursor.rowcount, 0)
        await self.connection.commit()
        return imported

    async def create_invite(
        self,
        nickname: str,
        *,
        expires_at: str | None = None,
        code: str | None = None,
    ) -> dict:
        await self.ensure_initialized()
        normalized_nickname = nickname.strip()
        if not normalized_nickname:
            raise ValueError("nickname is required")
        now = datetime.now(timezone.utc).isoformat()
        for _ in range(5):
            invite_code = code or self._generate_invite_code()
            invite_id = str(uuid.uuid4())
            user_id = str(uuid.uuid4())
            try:
                await self.connection.execute(
                    """
                    INSERT INTO invite_code (
                        id, code, user_id, nickname, enabled, expires_at, created_at, updated_at
                    ) VALUES (?, ?, ?, ?, 1, ?, ?, ?)
                    """,
                    (
                        invite_id,
                        invite_code,
                        user_id,
                        normalized_nickname,
                        expires_at,
                        now,
                        now,
                    ),
                )
                await self.connection.commit()
                return {
                    "id": invite_id,
                    "code": invite_code,
                    "user_id": user_id,
                    "nickname": normalized_nickname,
                    "enabled": True,
                    "expires_at": expires_at,
                    "claimed_at": None,
                    "last_claimed_at": None,
                    "claim_count": 0,
                    "created_at": now,
                    "updated_at": now,
                }
            except aiosqlite.IntegrityError:
                if code:
                    raise ValueError("invite code already exists")
        raise RuntimeError("failed to generate a unique invite code")

    async def claim_invite(self, code: str) -> dict | None:
        await self.ensure_initialized()
        normalized_code = code.strip()
        if not normalized_code:
            return None
        cursor = await self.connection.execute(
            "SELECT * FROM invite_code WHERE code = ?", (normalized_code,)
        )
        row = await cursor.fetchone()
        if not row or not row["enabled"] or self._invite_expired(row["expires_at"]):
            return None
        now = datetime.now(timezone.utc).isoformat()
        claimed_at = row["claimed_at"] or now
        await self.connection.execute(
            """
            UPDATE invite_code
            SET claimed_at = ?, last_claimed_at = ?, claim_count = claim_count + 1, updated_at = ?
            WHERE id = ?
            """,
            (claimed_at, now, now, row["id"]),
        )
        await self.connection.execute(
            """
            INSERT INTO app_user (user_id, source, nickname, created_at, last_seen_at)
            VALUES (?, 'invite', ?, ?, ?)
            ON CONFLICT(user_id) DO UPDATE SET
                source = 'invite', nickname = excluded.nickname, last_seen_at = excluded.last_seen_at
            """,
            (row["user_id"], row["nickname"], claimed_at, now),
        )
        await self.connection.commit()
        result = dict(row)
        result.update(
            claimed_at=claimed_at,
            last_claimed_at=now,
            claim_count=int(row["claim_count"]) + 1,
            enabled=bool(row["enabled"]),
        )
        return result

    async def is_valid_invited_user(self, user_id: str) -> bool:
        await self.ensure_initialized()
        cursor = await self.connection.execute(
            "SELECT enabled, expires_at FROM invite_code WHERE user_id = ?", (user_id,)
        )
        row = await cursor.fetchone()
        return bool(row and row["enabled"] and not self._invite_expired(row["expires_at"]))

    async def set_invite_enabled(self, invite_id: str, enabled: bool) -> dict | None:
        await self.ensure_initialized()
        now = datetime.now(timezone.utc).isoformat()
        await self.connection.execute(
            "UPDATE invite_code SET enabled = ?, updated_at = ? WHERE id = ?",
            (int(enabled), now, invite_id),
        )
        await self.connection.commit()
        cursor = await self.connection.execute(
            "SELECT * FROM invite_code WHERE id = ?", (invite_id,)
        )
        row = await cursor.fetchone()
        return self._invite_public_row(row) if row else None

    async def list_invites(self, *, page: int = 1, page_size: int = 20) -> dict:
        await self.ensure_initialized()
        safe_page = max(page, 1)
        safe_size = min(max(page_size, 1), 100)
        cursor = await self.connection.execute("SELECT COUNT(*) AS count FROM invite_code")
        total = int((await cursor.fetchone())["count"])
        cursor = await self.connection.execute(
            "SELECT * FROM invite_code ORDER BY created_at DESC LIMIT ? OFFSET ?",
            (safe_size, (safe_page - 1) * safe_size),
        )
        return {
            "items": [self._invite_public_row(row) for row in await cursor.fetchall()],
            "total": total,
            "page": safe_page,
            "page_size": safe_size,
        }

    @staticmethod
    def _generate_invite_code() -> str:
        alphabet = "23456789ABCDEFGHJKLMNPQRSTUVWXYZ"
        raw = "".join(secrets.choice(alphabet) for _ in range(8))
        return f"RUMI-{raw[:4]}-{raw[4:]}"

    @staticmethod
    def _invite_expired(expires_at: str | None) -> bool:
        if not expires_at:
            return False
        value = datetime.fromisoformat(expires_at.replace("Z", "+00:00"))
        if value.tzinfo is None:
            value = value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc) <= datetime.now(timezone.utc)

    @staticmethod
    def _invite_public_row(row: aiosqlite.Row) -> dict:
        data = dict(row)
        code = data.pop("code")
        parts = code.split("-")
        data["code_masked"] = (
            f"{parts[0]}-****-{parts[-1]}" if len(parts) >= 3 else f"****{code[-4:]}"
        )
        data["enabled"] = bool(data["enabled"])
        return data

    # --- Admin analytics ---

    async def get_admin_dashboard(self, *, days: int = 7) -> dict:
        await self.ensure_initialized()
        safe_days = 30 if days == 30 else 7
        start_modifier = f"-{safe_days - 1} days"
        active_sql = """
            SELECT w.user_id, w.created_at AS active_at FROM workspace w
            JOIN app_user u ON u.user_id = w.user_id
            UNION ALL
            SELECT w.user_id, d.created_at FROM document d
            JOIN workspace w ON w.id = d.workspace_id
            JOIN app_user u ON u.user_id = w.user_id
            UNION ALL
            SELECT w.user_id, m.created_at FROM message m
            JOIN workspace w ON w.id = m.workspace_id
            JOIN app_user u ON u.user_id = w.user_id
            WHERE m.role = 'human'
            UNION ALL
            SELECT w.user_id, t.created_at FROM task t
            JOIN workspace w ON w.id = t.workspace_id
            JOIN app_user u ON u.user_id = w.user_id
        """
        total_users = await self._admin_scalar(
            "SELECT COUNT(*) FROM app_user"
        )
        active_today = await self._admin_scalar(
            f"SELECT COUNT(DISTINCT user_id) FROM ({active_sql}) "
            "WHERE date(active_at) = date('now', 'localtime')"
        )
        active_7d = await self._admin_scalar(
            f"SELECT COUNT(DISTINCT user_id) FROM ({active_sql}) "
            "WHERE date(active_at) >= date('now', 'localtime', '-6 days')"
        )
        converted_users = await self._admin_scalar(
            """
            SELECT COUNT(DISTINCT w.user_id)
            FROM task t JOIN workspace w ON w.id = t.workspace_id
            JOIN app_user u ON u.user_id = w.user_id
            WHERE t.type = 'ppt' AND t.status = 'completed'
            """
        )
        completed_ppts = await self._admin_scalar(
            """
            SELECT COUNT(*) FROM task t
            JOIN workspace w ON w.id = t.workspace_id
            JOIN app_user u ON u.user_id = w.user_id
            WHERE type = 'ppt' AND status = 'completed'
              AND date(t.updated_at) >= date('now', 'localtime', ?)
            """,
            (start_modifier,),
        )
        completed_narrations = await self._admin_scalar(
            """
            SELECT COUNT(*) FROM task t
            JOIN workspace w ON w.id = t.workspace_id
            JOIN app_user u ON u.user_id = w.user_id
            WHERE type = 'narration' AND status = 'completed'
              AND date(t.updated_at) >= date('now', 'localtime', ?)
            """,
            (start_modifier,),
        )

        trends = await self._admin_trends(safe_days, active_sql)
        return {
            "range_days": safe_days,
            "kpis": {
                "total_users": total_users,
                "active_today": active_today,
                "active_7d": active_7d,
                "core_conversion_rate": round(
                    converted_users * 100 / total_users, 1
                )
                if total_users
                else 0.0,
                "completed_ppts": completed_ppts,
                "completed_narrations": completed_narrations,
            },
            "trends": trends,
        }

    async def list_admin_users(
        self, *, page: int = 1, page_size: int = 20, keyword: str = ""
    ) -> dict:
        await self.ensure_initialized()
        safe_page = max(page, 1)
        safe_size = min(max(page_size, 1), 100)
        pattern = f"%{keyword.strip()}%"
        where = "u.nickname LIKE ? OR u.user_id LIKE ?"
        cursor = await self.connection.execute(
            f"SELECT COUNT(*) AS count FROM app_user u WHERE {where}",
            (pattern, pattern),
        )
        total = int((await cursor.fetchone())["count"])
        cursor = await self.connection.execute(
            f"""
            SELECT
                u.user_id, u.nickname, u.source,
                COALESCE(i.claimed_at, u.created_at) AS claimed_at,
                COALESCE(i.last_claimed_at, u.last_seen_at) AS last_claimed_at,
                CASE WHEN u.source = 'open' THEN 1 ELSE COALESCE(i.enabled, 0) END AS enabled,
                (SELECT COUNT(*) FROM workspace w WHERE w.user_id = u.user_id) AS workspace_count,
                (SELECT COUNT(*) FROM document d JOIN workspace w ON w.id = d.workspace_id
                    WHERE w.user_id = u.user_id) AS document_count,
                (SELECT COUNT(*) FROM message m JOIN workspace w ON w.id = m.workspace_id
                    WHERE w.user_id = u.user_id AND m.role = 'human') AS message_count,
                (SELECT COUNT(*) FROM task t JOIN workspace w ON w.id = t.workspace_id
                    WHERE w.user_id = u.user_id AND t.type = 'ppt' AND t.status = 'completed') AS ppt_count,
                (SELECT COUNT(*) FROM task t JOIN workspace w ON w.id = t.workspace_id
                    WHERE w.user_id = u.user_id AND t.type = 'narration' AND t.status = 'completed') AS narration_count,
                (SELECT COUNT(*) FROM share_link s JOIN workspace w ON w.id = s.workspace_id
                    WHERE w.user_id = u.user_id) AS share_count,
                (SELECT MAX(active_at) FROM (
                    SELECT w.created_at AS active_at FROM workspace w WHERE w.user_id = u.user_id
                    UNION ALL
                    SELECT d.created_at FROM document d JOIN workspace w ON w.id = d.workspace_id
                        WHERE w.user_id = u.user_id
                    UNION ALL
                    SELECT m.created_at FROM message m JOIN workspace w ON w.id = m.workspace_id
                        WHERE w.user_id = u.user_id AND m.role = 'human'
                    UNION ALL
                    SELECT t.created_at FROM task t JOIN workspace w ON w.id = t.workspace_id
                        WHERE w.user_id = u.user_id
                )) AS last_active_at
            FROM app_user u
            LEFT JOIN invite_code i ON i.user_id = u.user_id
            WHERE {where}
            ORDER BY COALESCE(last_active_at, i.claimed_at, u.created_at) DESC
            LIMIT ? OFFSET ?
            """,
            (pattern, pattern, safe_size, (safe_page - 1) * safe_size),
        )
        items = []
        for row in await cursor.fetchall():
            item = dict(row)
            item["enabled"] = bool(item["enabled"])
            items.append(item)
        return {
            "items": items,
            "total": total,
            "page": safe_page,
            "page_size": safe_size,
        }

    async def _admin_trends(self, days: int, active_sql: str) -> list[dict]:
        start_modifier = f"-{days - 1} days"
        cursor = await self.connection.execute(
            f"""
            SELECT date(active_at) AS day, COUNT(DISTINCT user_id) AS count
            FROM ({active_sql})
            WHERE date(active_at) >= date('now', 'localtime', ?)
            GROUP BY date(active_at)
            """,
            (start_modifier,),
        )
        active = {row["day"]: int(row["count"]) for row in await cursor.fetchall()}

        async def daily_counts(sql: str) -> dict[str, int]:
            inner = await self.connection.execute(sql, (start_modifier,))
            return {row["day"]: int(row["count"]) for row in await inner.fetchall()}

        messages = await daily_counts(
            """
            SELECT date(m.created_at) AS day, COUNT(*) AS count FROM message m
            JOIN workspace w ON w.id = m.workspace_id
            JOIN app_user u ON u.user_id = w.user_id
            WHERE m.role = 'human' AND date(m.created_at) >= date('now', 'localtime', ?)
            GROUP BY date(m.created_at)
            """
        )
        documents = await daily_counts(
            """
            SELECT date(d.created_at) AS day, COUNT(*) AS count FROM document d
            JOIN workspace w ON w.id = d.workspace_id
            JOIN app_user u ON u.user_id = w.user_id
            WHERE date(d.created_at) >= date('now', 'localtime', ?)
            GROUP BY date(d.created_at)
            """
        )
        ppts = await daily_counts(
            """
            SELECT date(t.updated_at) AS day, COUNT(*) AS count FROM task t
            JOIN workspace w ON w.id = t.workspace_id
            JOIN app_user u ON u.user_id = w.user_id
            WHERE t.type = 'ppt' AND t.status = 'completed'
              AND date(t.updated_at) >= date('now', 'localtime', ?)
            GROUP BY date(t.updated_at)
            """
        )
        narrations = await daily_counts(
            """
            SELECT date(t.updated_at) AS day, COUNT(*) AS count FROM task t
            JOIN workspace w ON w.id = t.workspace_id
            JOIN app_user u ON u.user_id = w.user_id
            WHERE t.type = 'narration' AND t.status = 'completed'
              AND date(t.updated_at) >= date('now', 'localtime', ?)
            GROUP BY date(t.updated_at)
            """
        )
        today = datetime.now().date()
        result = []
        for offset in range(days - 1, -1, -1):
            day = (today - timedelta(days=offset)).isoformat()
            result.append(
                {
                    "date": day,
                    "active_users": active.get(day, 0),
                    "human_messages": messages.get(day, 0),
                    "documents": documents.get(day, 0),
                    "completed_ppts": ppts.get(day, 0),
                    "completed_narrations": narrations.get(day, 0),
                }
            )
        return result

    async def _admin_scalar(self, sql: str, params: tuple = ()) -> int:
        cursor = await self.connection.execute(sql, params)
        row = await cursor.fetchone()
        return int(row[0] or 0)

    # --- Workspace ---

    async def create_workspace(self, user_id: str, name: str) -> dict:
        normalized_name = name.strip()
        cursor = await self.connection.execute(
            "SELECT id FROM workspace WHERE user_id = ? AND lower(name) = lower(?)",
            (user_id, normalized_name),
        )
        existing = await cursor.fetchone()
        if existing:
            raise ValueError("Workspace name already exists")

        workspace_id = str(uuid.uuid4())
        default_voice_info = get_default_voice_info("Cherry")

        # Randomly pick a system style as default ppt_style
        default_style_id = "sys-swiss-modern"  # fallback
        try:
            cursor = await self.connection.execute(
                "SELECT id FROM ppt_style WHERE user_id = 'system'"
            )
            system_styles = await cursor.fetchall()
            if system_styles:
                default_style_id = random.choice(system_styles)["id"]
        except Exception:
            pass  # table may not exist yet during migration

        default_ext_data = json.dumps(
            {"ppt_style": default_style_id, "voice_info": default_voice_info},
            ensure_ascii=False,
        )
        await self.connection.execute(
            "INSERT INTO workspace (id, user_id, name, ext_data) VALUES (?, ?, ?, ?)",
            (workspace_id, user_id, normalized_name, default_ext_data),
        )
        await self.connection.commit()
        return {
            "id": workspace_id,
            "user_id": user_id,
            "name": normalized_name,
            "ext_data": json.loads(default_ext_data),
        }

    async def get_workspace(self, workspace_id: str) -> dict | None:
        cursor = await self.connection.execute(
            "SELECT * FROM workspace WHERE id = ?", (workspace_id,)
        )
        row = await cursor.fetchone()
        if not row:
            return None
        data = dict(row)
        # Parse ext_data JSON into dict
        raw_ext = data.get("ext_data")
        if isinstance(raw_ext, str):
            try:
                data["ext_data"] = json.loads(raw_ext)
            except (json.JSONDecodeError, TypeError):
                data["ext_data"] = {}
        elif raw_ext is None:
            data["ext_data"] = {}
        return data

    async def list_workspaces(self, user_id: str) -> list[dict]:
        cursor = await self.connection.execute(
            "SELECT * FROM workspace WHERE user_id = ? ORDER BY created_at DESC",
            (user_id,),
        )
        rows = await cursor.fetchall()
        results = []
        for row in rows:
            data = dict(row)
            raw_ext = data.get("ext_data")
            if isinstance(raw_ext, str):
                try:
                    data["ext_data"] = json.loads(raw_ext)
                except (json.JSONDecodeError, TypeError):
                    data["ext_data"] = {}
            elif raw_ext is None:
                data["ext_data"] = {}
            results.append(data)
        return results

    async def delete_workspace(self, workspace_id: str):
        # Delete all messages for this workspace
        await self.connection.execute(
            "DELETE FROM message WHERE workspace_id = ?", (workspace_id,)
        )
        # Delete all tasks for this workspace
        await self.connection.execute(
            "DELETE FROM task WHERE workspace_id = ?", (workspace_id,)
        )
        # Delete the workspace record
        await self.connection.execute(
            "DELETE FROM workspace WHERE id = ?", (workspace_id,)
        )
        await self.connection.commit()

    async def update_workspace_thread_id(self, workspace_id: str, thread_id: str):
        await self.connection.execute(
            "UPDATE workspace SET thread_id = ? WHERE id = ?",
            (thread_id, workspace_id),
        )
        await self.connection.commit()

    async def update_workspace_ext_data(self, workspace_id: str, key: str, value: Any):
        """Update a single key in workspace.ext_data JSON."""
        await self.ensure_initialized()
        cursor = await self.connection.execute(
            "SELECT ext_data FROM workspace WHERE id = ?", (workspace_id,)
        )
        row = await cursor.fetchone()
        if not row:
            raise ValueError("Workspace not found")
        raw = row["ext_data"]
        try:
            ext_data = json.loads(raw) if isinstance(raw, str) and raw else {}
        except (json.JSONDecodeError, TypeError):
            ext_data = {}
        ext_data[key] = value
        await self.connection.execute(
            "UPDATE workspace SET ext_data = ? WHERE id = ?",
            (json.dumps(ext_data, ensure_ascii=False), workspace_id),
        )
        await self.connection.commit()
        return ext_data

    # --- Message ---

    @staticmethod
    def _dump_json(value: Any) -> str:
        return json.dumps(value, ensure_ascii=False, default=str)

    @staticmethod
    def _load_json(value: str | None, fallback: Any) -> Any:
        if value is None:
            return fallback
        try:
            return json.loads(value)
        except json.JSONDecodeError:
            return fallback

    async def record_message(
        self,
        *,
        thread_id: str,
        workspace_id: str | None,
        run_id: str | None = None,
        message_id: str,
        role: str,
        content: Any,
        type: str | None = None,
        tool_calls: Any = None,
        tool_call_id: str | None = None,
        name: str | None = None,
        additional_kwargs: Any = None,
        response_metadata: Any = None,
    ) -> int:
        await self.ensure_initialized()
        now = datetime.now().isoformat()
        message_type = type or role
        cursor = await self.connection.execute(
            """
            INSERT INTO message (
                thread_id, workspace_id, run_id, message_id, role, type, content,
                tool_calls, tool_call_id, name, additional_kwargs, response_metadata,
                created_at, updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(thread_id, message_id, role) DO UPDATE SET
                workspace_id = excluded.workspace_id,
                run_id = COALESCE(message.run_id, excluded.run_id),
                type = excluded.type,
                content = excluded.content,
                tool_calls = excluded.tool_calls,
                tool_call_id = excluded.tool_call_id,
                name = excluded.name,
                additional_kwargs = excluded.additional_kwargs,
                response_metadata = excluded.response_metadata,
                updated_at = excluded.updated_at
            RETURNING id
            """,
            (
                thread_id,
                workspace_id,
                run_id,
                message_id,
                role,
                message_type,
                self._dump_json(content),
                self._dump_json(tool_calls) if tool_calls is not None else None,
                tool_call_id,
                name,
                self._dump_json(additional_kwargs or {}),
                self._dump_json(response_metadata or {}),
                now,
                now,
            ),
        )
        row = await cursor.fetchone()
        await self.connection.commit()
        return int(row["id"])

    async def list_thread_messages(
        self,
        thread_id: str,
        *,
        limit: int = 50,
        before: int | None = None,
    ) -> dict:
        """Return messages grouped by turn (human message + following AI/tool messages).

        ``limit`` controls the number of *turns* (not individual messages).
        ``before`` is the row ``id`` of the oldest human message from the previous page.
        """
        await self.ensure_initialized()
        safe_limit = min(max(limit, 1), 100)
        params: list[Any] = [thread_id]
        where = "thread_id = ?"
        if before is not None:
            where += " AND id < ?"
            params.append(before)

        # Step 1: find the N most recent human message ids (turn boundaries)
        cursor = await self.connection.execute(
            f"SELECT id FROM message WHERE {where} AND role = 'human' "
            f"ORDER BY id DESC LIMIT ?",
            [*params, safe_limit],
        )
        human_ids = sorted(row["id"] for row in await cursor.fetchall())

        if not human_ids:
            return {"messages": [], "next_cursor": None}

        # Step 2: fetch all messages from the oldest turn boundary onward
        # When ``before`` is set, apply it as an upper bound so that this
        # page does not overlap with the previous (newer) page's results.
        oldest_turn_id = human_ids[0]
        if before is not None:
            cursor = await self.connection.execute(
                "SELECT * FROM message WHERE thread_id = ? AND id >= ? AND id < ? ORDER BY id ASC",
                [thread_id, oldest_turn_id, before],
            )
        else:
            cursor = await self.connection.execute(
                "SELECT * FROM message WHERE thread_id = ? AND id >= ? ORDER BY id ASC",
                [thread_id, oldest_turn_id],
            )
        rows = await cursor.fetchall()
        messages = [self._message_row_to_dict(row, strip_tool_content=True) for row in rows]

        # Check whether there are older turns
        cursor = await self.connection.execute(
            "SELECT 1 FROM message WHERE thread_id = ? AND role = 'human' AND id < ? LIMIT 1",
            [thread_id, oldest_turn_id],
        )
        has_more = await cursor.fetchone() is not None

        return {
            "messages": messages,
            "next_cursor": int(oldest_turn_id) if has_more else None,
        }

    async def list_thread_history_runs(
        self,
        thread_id: str,
        *,
        limit: int = 10,
        before: int | None = None,
    ) -> dict:
        """Return chat history grouped by LangGraph run.

        ``limit`` controls the number of history runs. ``before`` is the
        ``first_row_id`` of the oldest run from the previous page. Messages
        without a run_id are grouped by the legacy human-turn boundary.
        """
        await self.ensure_initialized()
        safe_limit = min(max(limit, 1), 100)

        groups = await self._thread_history_run_groups(thread_id, before=before)
        if not groups:
            return {"runs": [], "next_cursor": None}

        page_groups = groups[:safe_limit]
        runs = []
        for group in reversed(page_groups):
            messages = await self._thread_history_run_messages(thread_id, group)
            if not messages:
                continue
            runs.append(
                {
                    "run_id": group["run_id"],
                    "thread_id": thread_id,
                    "workspace_id": group["workspace_id"],
                    "first_row_id": group["first_row_id"],
                    "last_row_id": group["last_row_id"],
                    "created_at": group["created_at"],
                    "updated_at": group["updated_at"],
                    "messages": messages,
                }
            )

        has_more = len(groups) > safe_limit
        next_cursor = page_groups[-1]["first_row_id"] if has_more else None
        return {"runs": runs, "next_cursor": next_cursor}

    async def _thread_history_run_groups(
        self,
        thread_id: str,
        *,
        before: int | None,
    ) -> list[dict]:
        params: list[Any] = [thread_id]
        before_clause = ""
        if before is not None:
            before_clause = "AND id < ?"
            params.append(before)

        cursor = await self.connection.execute(
            f"""
            SELECT
                run_id,
                MIN(id) AS first_row_id,
                MAX(id) AS last_row_id,
                MIN(created_at) AS created_at,
                MAX(updated_at) AS updated_at,
                MAX(workspace_id) AS workspace_id
            FROM message
            WHERE thread_id = ? AND run_id IS NOT NULL {before_clause}
            GROUP BY run_id
            """,
            params,
        )
        groups = [
            {
                "run_id": row["run_id"],
                "first_row_id": int(row["first_row_id"]),
                "last_row_id": int(row["last_row_id"]),
                "created_at": row["created_at"],
                "updated_at": row["updated_at"],
                "workspace_id": row["workspace_id"],
            }
            for row in await cursor.fetchall()
        ]

        groups.extend(await self._legacy_null_run_groups(thread_id, before=before))
        groups.sort(key=lambda group: group["last_row_id"], reverse=True)
        return groups

    async def _legacy_null_run_groups(
        self,
        thread_id: str,
        *,
        before: int | None,
    ) -> list[dict]:
        params: list[Any] = [thread_id]
        before_clause = ""
        if before is not None:
            before_clause = "AND id < ?"
            params.append(before)

        cursor = await self.connection.execute(
            f"""
            SELECT *
            FROM message
            WHERE thread_id = ? AND run_id IS NULL {before_clause}
            ORDER BY id ASC
            """,
            params,
        )
        rows = await cursor.fetchall()
        groups: list[dict] = []
        current_rows: list[aiosqlite.Row] = []

        for row in rows:
            if row["role"] == "human" and current_rows:
                groups.append(self._history_group_from_rows(None, current_rows))
                current_rows = []
            current_rows.append(row)

        if current_rows:
            groups.append(self._history_group_from_rows(None, current_rows))

        return groups

    def _history_group_from_rows(
        self,
        run_id: str | None,
        rows: list[aiosqlite.Row],
    ) -> dict:
        return {
            "run_id": run_id,
            "first_row_id": int(rows[0]["id"]),
            "last_row_id": int(rows[-1]["id"]),
            "created_at": rows[0]["created_at"],
            "updated_at": max(row["updated_at"] for row in rows),
            "workspace_id": next((row["workspace_id"] for row in rows if row["workspace_id"]), None),
        }

    async def _thread_history_run_messages(
        self,
        thread_id: str,
        group: dict,
    ) -> list[dict]:
        if group["run_id"] is not None:
            cursor = await self.connection.execute(
                "SELECT * FROM message WHERE thread_id = ? AND run_id = ? ORDER BY id ASC",
                [thread_id, group["run_id"]],
            )
        else:
            cursor = await self.connection.execute(
                """
                SELECT *
                FROM message
                WHERE thread_id = ? AND run_id IS NULL AND id >= ? AND id <= ?
                ORDER BY id ASC
                """,
                [thread_id, group["first_row_id"], group["last_row_id"]],
            )
        rows = await cursor.fetchall()
        return [self._message_row_to_dict(row, strip_tool_content=True) for row in rows]

    def _message_row_to_dict(self, row: aiosqlite.Row, *, strip_tool_content: bool = False) -> dict:
        content = self._load_json(row["content"], "")
        # Strip tool message content in list response to reduce payload size;
        # content can be fetched individually via the detail endpoint.
        if strip_tool_content and row["role"] == "tool":
            content = ""
        return {
            "id": int(row["id"]),
            "thread_id": row["thread_id"],
            "workspace_id": row["workspace_id"],
            "run_id": row["run_id"],
            "message_id": row["message_id"],
            "role": row["role"],
            "type": row["type"],
            "content": content,
            "tool_calls": self._load_json(row["tool_calls"], []),
            "tool_call_id": row["tool_call_id"],
            "name": row["name"],
            "additional_kwargs": self._load_json(row["additional_kwargs"], {}),
            "response_metadata": self._load_json(row["response_metadata"], {}),
            "created_at": row["created_at"],
            "updated_at": row["updated_at"],
        }

    async def get_message_by_id(self, message_id: str, thread_id: str) -> dict | None:
        """Fetch a single message by its message_id within the given thread."""
        await self.ensure_initialized()
        cursor = await self.connection.execute(
            "SELECT * FROM message WHERE message_id = ? AND thread_id = ?",
            [message_id, thread_id],
        )
        row = await cursor.fetchone()
        if row is None:
            return None
        return self._message_row_to_dict(row)

    # --- Document ---


    async def create_document(
        self,
        workspace_id: str,
        filename: str,
        file_type: str,
        storage_path: str,
        content_hash: str = "",
        progress_data: dict | None = None,
    ) -> dict:
        doc_id = str(uuid.uuid4())
        now = datetime.now().isoformat()
        initial_progress = progress_data or {
            "stage": "uploaded",
            "stage_label": "等待解析",
            "percent": 0,
            "message": "文档已上传，等待解析",
            "current": 0,
            "total": 0,
            "updated_at": now,
        }
        initial_progress["updated_at"] = now
        await self.connection.execute(
            "INSERT INTO document (id, workspace_id, filename, file_type, storage_path, content_hash, status, progress_data, created_at, updated_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                doc_id,
                workspace_id,
                filename,
                file_type,
                storage_path,
                content_hash,
                "uploaded",
                json.dumps(initial_progress, ensure_ascii=False),
                now,
                now,
            ),
        )
        await self.connection.commit()
        return {
            "id": doc_id,
            "workspace_id": workspace_id,
            "filename": filename,
            "file_type": file_type,
            "storage_path": storage_path,
            "content_hash": content_hash,
            "summary": None,
            "status": "uploaded",
            "error_message": None,
            "progress_data": json.dumps(initial_progress, ensure_ascii=False),
            "created_at": now,
            "updated_at": now,
        }

    async def find_duplicate_document(
        self, workspace_id: str, filename: str, content_hash: str
    ) -> dict | None:
        """Find an existing non-error document with the same filename or content_hash.

        Returns the conflicting document dict, or None if no duplicate found.
        """
        await self.ensure_initialized()
        cursor = await self.connection.execute(
            "SELECT * FROM document "
            "WHERE workspace_id = ? AND status != 'error' "
            "AND (filename = ? OR content_hash = ?) "
            "ORDER BY created_at DESC LIMIT 1",
            (workspace_id, filename, content_hash),
        )
        row = await cursor.fetchone()
        return dict(row) if row else None

    async def list_documents(self, workspace_id: str) -> list[dict]:
        cursor = await self.connection.execute(
            "SELECT * FROM document WHERE workspace_id = ? ORDER BY created_at DESC",
            (workspace_id,),
        )
        rows = await cursor.fetchall()
        return [dict(row) for row in rows]

    async def update_document(self, doc_id: str, **kwargs):
        kwargs["updated_at"] = datetime.now().isoformat()
        sets = ", ".join(f"{key} = ?" for key in kwargs)
        values = list(kwargs.values()) + [doc_id]
        await self.connection.execute(
            f"UPDATE document SET {sets} WHERE id = ?", values
        )
        await self.connection.commit()

    async def delete_document(self, doc_id: str, workspace_id: str = None):
        if workspace_id:
            await self.connection.execute(
                "DELETE FROM document WHERE id = ? AND workspace_id = ?",
                (doc_id, workspace_id),
            )
        else:
            await self.connection.execute("DELETE FROM document WHERE id = ?", (doc_id,))
        await self.connection.commit()

    # --- Task ---

    async def create_task(
        self, workspace_id: str, type: str, title: str = None, parent_task_id: str = None
    ) -> dict:
        task_id = str(uuid.uuid4())
        await self.connection.execute(
            "INSERT INTO task (id, workspace_id, type, title, parent_task_id) VALUES (?, ?, ?, ?, ?)",
            (task_id, workspace_id, type, title, parent_task_id),
        )
        await self.connection.commit()
        return {
            "id": task_id,
            "workspace_id": workspace_id,
            "type": type,
            "title": title,
            "parent_task_id": parent_task_id,
            "status": "generating",
        }

    async def list_tasks(self, workspace_id: str) -> list[dict]:
        # Only return top-level tasks (PPT), nest children
        cursor = await self.connection.execute(
            "SELECT * FROM task WHERE workspace_id = ? AND parent_task_id IS NULL ORDER BY created_at DESC",
            (workspace_id,),
        )
        parents = [dict(row) for row in await cursor.fetchall()]

        if parents:
            parent_ids = [p["id"] for p in parents]
            placeholders = ",".join("?" * len(parent_ids))
            cursor = await self.connection.execute(
                f"SELECT * FROM task WHERE parent_task_id IN ({placeholders}) ORDER BY created_at",
                parent_ids,
            )
            children_map: dict[str, list[dict]] = {}
            for row in await cursor.fetchall():
                child = dict(row)
                children_map.setdefault(child["parent_task_id"], []).append(child)
            for parent in parents:
                parent["children"] = children_map.get(parent["id"], [])

        return parents

    async def get_task(self, task_id: str) -> dict | None:
        """Get a single task by ID."""
        await self.ensure_initialized()
        cursor = await self.connection.execute(
            "SELECT * FROM task WHERE id = ?", (task_id,)
        )
        row = await cursor.fetchone()
        if not row:
            return None
        task = dict(row)
        # Attach children
        cursor = await self.connection.execute(
            "SELECT * FROM task WHERE parent_task_id = ? ORDER BY created_at",
            (task_id,),
        )
        task["children"] = [dict(r) for r in await cursor.fetchall()]
        return task

    async def get_task_result_data(self, task_id: str) -> dict:
        """Get parsed result_data for a task."""
        await self.ensure_initialized()
        cursor = await self.connection.execute(
            "SELECT result_data FROM task WHERE id = ?", (task_id,)
        )
        row = await cursor.fetchone()
        if not row or not row["result_data"]:
            return {}
        try:
            return json.loads(row["result_data"])
        except (json.JSONDecodeError, TypeError):
            return {}

    async def update_task(self, task_id: str, **kwargs):
        kwargs["updated_at"] = datetime.now().isoformat()
        sets = ", ".join(f"{key} = ?" for key in kwargs)
        values = list(kwargs.values()) + [task_id]
        await self.connection.execute(
            f"UPDATE task SET {sets} WHERE id = ?", values
        )
        await self.connection.commit()

    async def delete_task(self, task_id: str) -> list[str]:
        """Delete a task. If PPT, also delete all child tasks (cascade).

        Returns list of deleted task IDs.
        """
        # Get task info
        cursor = await self.connection.execute(
            "SELECT id, type FROM task WHERE id = ?", (task_id,)
        )
        task = await cursor.fetchone()
        if not task:
            return []

        deleted_ids: list[str] = [task_id]

        if task["type"] == "ppt":
            # Cascade: find and delete all child tasks
            cursor = await self.connection.execute(
                "SELECT id FROM task WHERE parent_task_id = ?", (task_id,)
            )
            children = await cursor.fetchall()
            for child in children:
                deleted_ids.append(child["id"])
            await self.connection.execute(
                "DELETE FROM task WHERE parent_task_id = ?", (task_id,)
            )

        await self.connection.execute("DELETE FROM task WHERE id = ?", (task_id,))
        await self.connection.commit()
        return deleted_ids

    # --- Share Links ---

    async def create_or_get_active_share(self, task: dict) -> dict:
        """Create a share link or return the active one for a task."""
        await self.ensure_initialized()
        cursor = await self.connection.execute(
            "SELECT * FROM share_link WHERE task_id = ? AND revoked_at IS NULL ORDER BY created_at DESC LIMIT 1",
            (task["id"],),
        )
        row = await cursor.fetchone()
        if row:
            return dict(row)

        token = secrets.token_urlsafe(32)
        await self.connection.execute(
            "INSERT INTO share_link (token, task_id, workspace_id, type) VALUES (?, ?, ?, ?)",
            (token, task["id"], task["workspace_id"], task["type"]),
        )
        await self.connection.commit()
        cursor = await self.connection.execute(
            "SELECT * FROM share_link WHERE token = ?",
            (token,),
        )
        row = await cursor.fetchone()
        return dict(row)

    async def get_active_share_by_task(self, task_id: str) -> dict | None:
        await self.ensure_initialized()
        cursor = await self.connection.execute(
            "SELECT * FROM share_link WHERE task_id = ? AND revoked_at IS NULL ORDER BY created_at DESC LIMIT 1",
            (task_id,),
        )
        row = await cursor.fetchone()
        return dict(row) if row else None

    async def get_active_share_by_token(self, token: str) -> dict | None:
        await self.ensure_initialized()
        cursor = await self.connection.execute(
            "SELECT * FROM share_link WHERE token = ? AND revoked_at IS NULL",
            (token,),
        )
        row = await cursor.fetchone()
        return dict(row) if row else None

    async def revoke_share_for_task(self, task_id: str, reason: str = "user_revoked") -> int:
        await self.ensure_initialized()
        now = datetime.now().isoformat()
        cursor = await self.connection.execute(
            "UPDATE share_link SET revoked_at = ?, revoked_reason = ? WHERE task_id = ? AND revoked_at IS NULL",
            (now, reason, task_id),
        )
        await self.connection.commit()
        return cursor.rowcount

    async def revoke_shares_for_tasks(self, task_ids: list[str], reason: str = "task_deleted") -> int:
        await self.ensure_initialized()
        if not task_ids:
            return 0
        placeholders = ",".join("?" * len(task_ids))
        now = datetime.now().isoformat()
        cursor = await self.connection.execute(
            f"UPDATE share_link SET revoked_at = ?, revoked_reason = ? WHERE task_id IN ({placeholders}) AND revoked_at IS NULL",
            [now, reason, *task_ids],
        )
        await self.connection.commit()
        return cursor.rowcount

    # --- PPT Style ---

    async def list_ppt_styles(self, user_id: str) -> list[dict]:
        """List styles for a user (without style_description)."""
        await self.ensure_initialized()
        cursor = await self.connection.execute(
            "SELECT id, user_id, category, name, name_en, description, preview_path, created_at "
            "FROM ppt_style WHERE user_id = ? ORDER BY category, name_en",
            (user_id,),
        )
        return [dict(row) for row in await cursor.fetchall()]

    async def list_all_ppt_styles(self, user_ids: list[str]) -> list[dict]:
        """List styles for multiple user_ids (without style_description)."""
        await self.ensure_initialized()
        if not user_ids:
            return []
        placeholders = ",".join("?" * len(user_ids))
        cursor = await self.connection.execute(
            f"SELECT id, user_id, category, name, name_en, description, preview_path, created_at "
            f"FROM ppt_style WHERE user_id IN ({placeholders}) ORDER BY category, name_en",
            user_ids,
        )
        return [dict(row) for row in await cursor.fetchall()]

    async def get_ppt_style_by_name_en(self, name_en: str, user_id: str | None = None) -> dict | None:
        """Get a single style by name_en. If user_id given, prefer user custom over system."""
        await self.ensure_initialized()
        if user_id:
            cursor = await self.connection.execute(
                "SELECT * FROM ppt_style WHERE name_en = ? AND user_id IN (?, 'system') "
                "ORDER BY CASE WHEN user_id = ? THEN 0 ELSE 1 END LIMIT 1",
                (name_en, user_id, user_id),
            )
        else:
            cursor = await self.connection.execute(
                "SELECT * FROM ppt_style WHERE name_en = ? LIMIT 1",
                (name_en,),
            )
        row = await cursor.fetchone()
        return dict(row) if row else None

    async def create_ppt_style(
        self,
        user_id: str,
        category: str,
        name: str,
        name_en: str = "",
        description: str = "",
        style_description: str = "",
        preview_path: str = "",
    ) -> dict:
        await self.ensure_initialized()
        style_id = str(uuid.uuid4())
        await self.connection.execute(
            "INSERT INTO ppt_style (id, user_id, category, name, name_en, description, style_description, preview_path) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (style_id, user_id, category, name, name_en, description, style_description, preview_path),
        )
        await self.connection.commit()
        return {
            "id": style_id,
            "user_id": user_id,
            "category": category,
            "name": name,
            "name_en": name_en,
            "description": description,
            "style_description": style_description,
            "preview_path": preview_path,
        }

    async def get_ppt_style(self, style_id: str) -> dict | None:
        """Get a single style by id."""
        await self.ensure_initialized()
        cursor = await self.connection.execute(
            "SELECT * FROM ppt_style WHERE id = ?", (style_id,)
        )
        row = await cursor.fetchone()
        return dict(row) if row else None

    async def delete_ppt_style(self, style_id: str):
        await self.ensure_initialized()
        await self.connection.execute("DELETE FROM ppt_style WHERE id = ?", (style_id,))
        await self.connection.commit()

    async def update_ppt_style_preview_path(self, style_id: str, preview_path: str):
        """Update a style's preview_path to an independent location."""
        await self.ensure_initialized()
        await self.connection.execute(
            "UPDATE ppt_style SET preview_path = ? WHERE id = ?",
            (preview_path, style_id),
        )
        await self.connection.commit()

    async def update_ppt_style(self, style_id: str, **fields):
        """Update arbitrary fields of a ppt_style record."""
        if not fields:
            return
        await self.ensure_initialized()
        set_clause = ", ".join(f"{k} = ?" for k in fields)
        values = list(fields.values()) + [style_id]
        await self.connection.execute(
            f"UPDATE ppt_style SET {set_clause} WHERE id = ?",
            values,
        )
        await self.connection.commit()
