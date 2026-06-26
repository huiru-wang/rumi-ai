"""Unified file storage facade.

Delegates to a `StorageProvider` (local or OSS) and provides smart routing
that transparently handles legacy absolute paths stored in the database.

Path structure (both local and OSS):
    user/{user_id}/workspace/{workspace_id}/docs/{filename}         — documents
    user/{user_id}/workspace/{workspace_id}/ppt/{task_id}/{...}     — PPT & narration
    user/{user_id}/workspace/{workspace_id}/style/{task_id}/...     — style extraction
    user/{user_id}/style/{style_id}/{filename}                      — custom styles
"""

from __future__ import annotations

import asyncio
import shutil
from pathlib import Path
from typing import TYPE_CHECKING

from src.storage.providers import LocalProvider, StorageProvider

if TYPE_CHECKING:
    from src.storage.database import Database


class FileStore:
    """High-level file storage interface used throughout the application.

    Parameters
    ----------
    base_dir:
        Root directory for local file storage (e.g. ``data/files``).
    provider:
        Storage provider instance. Defaults to ``LocalProvider(base_dir)``.
    db:
        Database instance for resolving ``user_id`` from ``workspace_id``.
        Required for the new path structure; optional for backward compat.

    Smart routing
    -------------
    Methods that accept a *path_or_key* argument accept either:
    - an absolute local path (legacy DB records), or
    - a relative key (``user/{user_id}/workspace/...``).

    The store automatically routes legacy absolute paths to the local
    filesystem, even when the active provider is OSS.
    """

    def __init__(
        self,
        base_dir: str,
        provider: StorageProvider | None = None,
        db: Database | None = None,
    ):
        self.base_dir = Path(base_dir)
        self.base_dir.mkdir(parents=True, exist_ok=True)
        self._provider: StorageProvider = provider or LocalProvider(base_dir)
        self._db = db
        # Always keep a local provider for legacy path resolution
        if isinstance(self._provider, LocalProvider):
            self._local: LocalProvider = self._provider
        else:
            self._local = LocalProvider(base_dir)

    # ------------------------------------------------------------------
    # User / workspace resolution
    # ------------------------------------------------------------------

    async def _resolve_user_id(self, workspace_id: str) -> str:
        """Resolve user_id from workspace_id via DB lookup."""
        if self._db is None:
            raise RuntimeError(
                "FileStore requires a Database instance to resolve user_id. "
                "Pass db=... when constructing FileStore."
            )
        ws = await self._db.get_workspace(workspace_id)
        if not ws:
            raise ValueError(f"Workspace not found: {workspace_id}")
        return ws["user_id"]

    def _ws_prefix(self, user_id: str, workspace_id: str) -> str:
        """Build the common path prefix: user/{user_id}/workspace/{workspace_id}."""
        return f"user/{user_id}/workspace/{workspace_id}"

    # ------------------------------------------------------------------
    # Path routing helpers
    # ------------------------------------------------------------------

    def is_local_path(self, path_or_key: str) -> bool:
        """Return True if *path_or_key* refers to a local file (not an OSS key)."""
        if self._provider.is_local:
            return True
        if path_or_key.startswith(str(self.base_dir)):
            return True
        return False

    def get_file_url(self, path_or_key: str) -> str:
        """Return a URL (local path or signed URL) for accessing a file."""
        if self.is_local_path(path_or_key):
            return path_or_key
        return self._provider.get_url(path_or_key)

    def get_public_url(self, path_or_key: str) -> str:
        """Return a permanent public URL for the file.

        - Local: returns absolute local path
        - OSS: returns public read URL (https://{bucket}.{endpoint}/{key})
        """
        if self.is_local_path(path_or_key):
            return path_or_key
        return self._provider.get_public_url(path_or_key)

    # ------------------------------------------------------------------
    # Core write operations (new path structure)
    # ------------------------------------------------------------------

    async def save_doc(
        self, workspace_id: str, filename: str, content: bytes
    ) -> str:
        """Save a document source file under docs/."""
        user_id = await self._resolve_user_id(workspace_id)
        key = f"{self._ws_prefix(user_id, workspace_id)}/docs/{filename}"
        return await self._provider.save_async(key, content)

    async def save_ppt_file(
        self, workspace_id: str, task_id: str, filename: str, content: bytes
    ) -> str:
        """Save a PPT output file under ppt/{task_id}/."""
        user_id = await self._resolve_user_id(workspace_id)
        key = f"{self._ws_prefix(user_id, workspace_id)}/ppt/{task_id}/{filename}"
        return await self._provider.save_async(key, content)

    async def save_style_output(
        self, workspace_id: str, task_id: str, filename: str, content: bytes
    ) -> str:
        """Save a style extraction output file under style/{task_id}/."""
        user_id = await self._resolve_user_id(workspace_id)
        key = f"{self._ws_prefix(user_id, workspace_id)}/style/{task_id}/{filename}"
        return await self._provider.save_async(key, content)

    # Legacy-compatible save (backward compat, prefer typed methods above)
    def save(self, workspace_id: str, filename: str, content: bytes) -> str:
        """Save file synchronously with legacy flat path. Prefer typed async methods."""
        key = f"{workspace_id}/{filename}"
        return self._provider.save(key, content)

    async def save_async(self, workspace_id: str, filename: str, content: bytes) -> str:
        """Save file asynchronously with auto user_id resolution."""
        user_id = await self._resolve_user_id(workspace_id)
        key = f"{self._ws_prefix(user_id, workspace_id)}/{filename}"
        return await self._provider.save_async(key, content)

    # ------------------------------------------------------------------
    # Read operations (smart routing)
    # ------------------------------------------------------------------

    async def read(self, path_or_key: str) -> bytes:
        """Read file content as bytes."""
        if self.is_local_path(path_or_key):
            return await self._local.read(path_or_key)
        return await self._provider.read(path_or_key)

    async def read_text(self, path_or_key: str, encoding: str = "utf-8") -> str:
        """Read file content as text."""
        data = await self.read(path_or_key)
        return data.decode(encoding)

    async def exists(self, path_or_key: str) -> bool:
        """Check whether a file exists."""
        if self.is_local_path(path_or_key):
            return await self._local.exists(path_or_key)
        return await self._provider.exists(path_or_key)

    # ------------------------------------------------------------------
    # Write-text convenience (for editing saved files)
    # ------------------------------------------------------------------

    async def write_text(self, path_or_key: str, text: str, encoding: str = "utf-8") -> None:
        """Overwrite a text file in-place."""
        content = text.encode(encoding)
        if self.is_local_path(path_or_key):
            file_path = self._local._resolve(path_or_key)

            def _write():
                file_path.parent.mkdir(parents=True, exist_ok=True)
                file_path.write_bytes(content)

            await asyncio.to_thread(_write)
        else:
            await self._provider.save_async(path_or_key, content)

    # ------------------------------------------------------------------
    # Delete operations (smart routing)
    # ------------------------------------------------------------------

    def delete(self, file_path: str) -> None:
        """Delete a single file synchronously."""
        p = Path(file_path)
        if p.is_absolute():
            if p.exists():
                p.unlink()
        else:
            full = self.base_dir / file_path
            if full.exists():
                full.unlink()

    async def delete_async(self, path_or_key: str) -> None:
        """Delete a single file asynchronously."""
        if self.is_local_path(path_or_key):
            await self._local.delete(path_or_key)
        else:
            await self._provider.delete(path_or_key)

    def delete_workspace(self, workspace_id: str) -> None:
        """Delete the entire workspace directory synchronously (local only, legacy)."""
        workspace_dir = self.base_dir / workspace_id
        if workspace_dir.exists():
            shutil.rmtree(workspace_dir)

    async def delete_workspace_async(self, workspace_id: str) -> None:
        """Delete all files for a workspace (works for both local and OSS)."""
        if self._db:
            user_id = await self._resolve_user_id(workspace_id)
            prefix = f"user/{user_id}/workspace/{workspace_id}/"
            if not self._provider.is_local:
                await self._provider.delete_prefix(prefix)
            # Clean up new-path local directory
            new_dir = self.base_dir / prefix.rstrip("/")
            if new_dir.exists():
                shutil.rmtree(new_dir, ignore_errors=True)
            # Also try legacy path for backward compatibility
            legacy_dir = self.base_dir / workspace_id
            if legacy_dir.exists():
                shutil.rmtree(legacy_dir, ignore_errors=True)
        else:
            # Fallback: legacy behavior
            if self._provider.is_local:
                workspace_dir = self.base_dir / workspace_id

                def _rmtree():
                    if workspace_dir.exists():
                        shutil.rmtree(workspace_dir, ignore_errors=True)

                await asyncio.to_thread(_rmtree)
            else:
                await self._provider.delete_prefix(f"{workspace_id}/")
                workspace_dir = self.base_dir / workspace_id
                if workspace_dir.exists():
                    shutil.rmtree(workspace_dir, ignore_errors=True)

    async def delete_dir(self, path_or_key: str) -> None:
        """Delete a directory and all its contents."""
        if self.is_local_path(path_or_key):
            dir_path = Path(path_or_key)

            def _rmtree():
                if dir_path.exists():
                    shutil.rmtree(dir_path, ignore_errors=True)

            await asyncio.to_thread(_rmtree)
        else:
            prefix = path_or_key.rstrip("/") + "/"
            await self._provider.delete_prefix(prefix)

    async def delete_ppt_task_dir(self, workspace_id: str, task_id: str) -> None:
        """Delete a PPT task's output directory: ppt/{task_id}/."""
        user_id = await self._resolve_user_id(workspace_id)
        prefix = f"user/{user_id}/workspace/{workspace_id}/ppt/{task_id}/"
        if not self._provider.is_local:
            await self._provider.delete_prefix(prefix)
        # Also clean local
        local_dir = self.base_dir / prefix.rstrip("/")
        if local_dir.exists():
            shutil.rmtree(local_dir, ignore_errors=True)

    async def delete_style_task_dir(self, workspace_id: str, task_id: str) -> None:
        """Delete a style extraction task's output directory: style/{task_id}/."""
        user_id = await self._resolve_user_id(workspace_id)
        prefix = f"user/{user_id}/workspace/{workspace_id}/style/{task_id}/"
        if not self._provider.is_local:
            await self._provider.delete_prefix(prefix)
        # Also clean local
        local_dir = self.base_dir / prefix.rstrip("/")
        if local_dir.exists():
            shutil.rmtree(local_dir, ignore_errors=True)

    # ------------------------------------------------------------------
    # User style helpers  (user/{user_id}/style/{style_id}/)
    # ------------------------------------------------------------------

    async def save_user_style(
        self, user_id: str, style_id: str, filename: str, content: bytes
    ) -> str:
        """Save a user style preview file.

        Returns the absolute path (local) or OSS key of the saved file.
        """
        key = f"user/{user_id}/style/{style_id}/{filename}"
        return await self._provider.save_async(key, content)

    async def copy_to_user_style(
        self, source_path: str, user_id: str, style_id: str, filename: str
    ) -> str:
        """Copy a file from an existing location to user style storage."""
        content = await self.read(source_path)
        return await self.save_user_style(user_id, style_id, filename, content)

    async def delete_user_style(self, user_id: str, style_id: str) -> None:
        """Delete an entire user style directory."""
        prefix = f"user/{user_id}/style/{style_id}/"
        if self._provider.is_local:
            dir_path = self.base_dir / prefix.rstrip("/")

            def _rmtree():
                if dir_path.exists():
                    shutil.rmtree(dir_path, ignore_errors=True)

            await asyncio.to_thread(_rmtree)
        else:
            await self._provider.delete_prefix(prefix)
