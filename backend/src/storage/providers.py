"""Storage provider abstraction layer.

Provides a unified interface for local filesystem and Alibaba Cloud OSS storage,
allowing seamless switching via environment configuration.
"""

import asyncio
import logging
import shutil
from abc import ABC, abstractmethod
from pathlib import Path

logger = logging.getLogger(__name__)


class StorageProvider(ABC):
    """Storage provider abstract interface.

    All methods accept a `key` which is a relative path like `{workspace_id}/{filename}`.
    `save()` returns a storage identifier:
      - LocalProvider: absolute filesystem path
      - OSSProvider:   the OSS object key itself
    """

    @abstractmethod
    def save(self, key: str, content: bytes) -> str:
        """Save file synchronously, return storage identifier."""
        ...

    @abstractmethod
    async def save_async(self, key: str, content: bytes) -> str:
        """Save file asynchronously, return storage identifier."""
        ...

    @abstractmethod
    async def read(self, key: str) -> bytes:
        """Read file content."""
        ...

    @abstractmethod
    async def exists(self, key: str) -> bool:
        """Check if file exists."""
        ...

    @abstractmethod
    async def delete(self, key: str) -> None:
        """Delete a single file."""
        ...

    @abstractmethod
    async def delete_prefix(self, prefix: str) -> None:
        """Delete all files whose key starts with `prefix`."""
        ...

    @abstractmethod
    def get_url(self, key: str) -> str:
        """Return a URL for accessing the file (local path or signed URL)."""
        ...

    @abstractmethod
    def get_public_url(self, key: str) -> str:
        """Return a permanent public URL for the file.

        - LocalProvider: returns absolute local path (same as get_url)
        - OSSProvider: returns public read URL (https://{bucket}.{endpoint}/{key})
        """
        ...

    @property
    @abstractmethod
    def is_local(self) -> bool:
        """Return True if this provider stores files on the local filesystem."""
        ...


# ---------------------------------------------------------------------------
# Local filesystem provider
# ---------------------------------------------------------------------------

class LocalProvider(StorageProvider):
    """Local filesystem storage provider.

    `key` is a relative path; files are stored under `base_dir / key`.
    Public methods accept both relative keys and absolute paths (for legacy DB records).
    """

    def __init__(self, base_dir: str):
        self.base_dir = Path(base_dir)
        self.base_dir.mkdir(parents=True, exist_ok=True)

    def _resolve(self, key_or_path: str) -> Path:
        """Resolve a relative key or absolute path to a concrete Path."""
        p = Path(key_or_path)
        if p.is_absolute():
            return p
        # Check if the relative path already includes base_dir prefix
        # (e.g. returned by save() which returns str(base_dir / key))
        try:
            p.relative_to(self.base_dir)
            return p  # Already starts with base_dir
        except ValueError:
            pass
        return self.base_dir / key_or_path

    # -- write --

    def save(self, key: str, content: bytes) -> str:
        file_path = self.base_dir / key
        file_path.parent.mkdir(parents=True, exist_ok=True)
        file_path.write_bytes(content)
        return str(file_path)

    async def save_async(self, key: str, content: bytes) -> str:
        file_path = self.base_dir / key

        def _write():
            file_path.parent.mkdir(parents=True, exist_ok=True)
            file_path.write_bytes(content)

        await asyncio.to_thread(_write)
        return str(file_path)

    # -- read --

    async def read(self, key: str) -> bytes:
        file_path = self._resolve(key)

        def _read():
            return file_path.read_bytes()

        return await asyncio.to_thread(_read)

    async def exists(self, key: str) -> bool:
        return self._resolve(key).exists()

    # -- delete --

    async def delete(self, key: str) -> None:
        file_path = self._resolve(key)

        def _delete():
            if file_path.exists():
                file_path.unlink()

        await asyncio.to_thread(_delete)

    async def delete_prefix(self, prefix: str) -> None:
        dir_path = self._resolve(prefix)

        def _rmtree():
            if dir_path.exists():
                shutil.rmtree(dir_path, ignore_errors=True)

        await asyncio.to_thread(_rmtree)

    # -- url --

    def get_url(self, key: str) -> str:
        """Return the absolute local path (served via /api/files/ route)."""
        return str(self._resolve(key))

    def get_public_url(self, key: str) -> str:
        """Local files: return absolute path (same as get_url)."""
        return str(self._resolve(key))

    @property
    def is_local(self) -> bool:
        return True


# ---------------------------------------------------------------------------
# Alibaba Cloud OSS provider
# ---------------------------------------------------------------------------

class OSSProvider(StorageProvider):
    """Alibaba Cloud OSS storage provider.

    `key` maps directly to an OSS object key.
    All blocking oss2 SDK calls are wrapped in `asyncio.to_thread`.
    """

    # Signed URL expiry in seconds (1 hour)
    _SIGN_URL_EXPIRY = 3600

    def __init__(
        self,
        endpoint: str,
        bucket: str,
        access_key_id: str,
        access_key_secret: str,
    ):
        try:
            import oss2  # type: ignore
        except ImportError as exc:
            raise RuntimeError(
                "oss2 package is required for OSS storage. "
                "Install it with: uv add oss2"
            ) from exc

        self._endpoint = endpoint
        self._bucket_name = bucket
        self._auth = oss2.Auth(access_key_id, access_key_secret)
        self._bucket = oss2.Bucket(self._auth, endpoint, bucket)
        self._oss2 = oss2

    # -- write --

    def save(self, key: str, content: bytes) -> str:
        self._bucket.put_object(key, content)
        logger.debug("[OSSProvider] saved: %s (%d bytes)", key, len(content))
        return key

    async def save_async(self, key: str, content: bytes) -> str:
        await asyncio.to_thread(self._bucket.put_object, key, content)
        logger.debug("[OSSProvider] saved: %s (%d bytes)", key, len(content))
        return key

    # -- read --

    async def read(self, key: str) -> bytes:
        def _get():
            result = self._bucket.get_object(key)
            return result.read()

        return await asyncio.to_thread(_get)

    async def exists(self, key: str) -> bool:
        return await asyncio.to_thread(self._bucket.object_exists, key)

    # -- delete --

    async def delete(self, key: str) -> None:
        await asyncio.to_thread(self._bucket.delete_object, key)
        logger.debug("[OSSProvider] deleted: %s", key)

    async def delete_prefix(self, prefix: str) -> None:
        def _delete_all():
            count = 0
            for obj in self._oss2.ObjectIterator(self._bucket, prefix=prefix):
                self._bucket.delete_object(obj.key)
                count += 1
            return count

        count = await asyncio.to_thread(_delete_all)
        logger.debug("[OSSProvider] deleted %d objects with prefix: %s", count, prefix)

    # -- url --

    def get_url(self, key: str) -> str:
        """Return a pre-signed URL for temporary access."""
        return self._bucket.sign_url("GET", key, self._SIGN_URL_EXPIRY)

    def get_public_url(self, key: str) -> str:
        """Return a permanent public read URL.

        Format: https://{bucket}.{endpoint}/{key}
        Assumes the OSS bucket is configured for public read access.
        """
        # Strip protocol from endpoint to build the URL
        host = self._endpoint.replace("https://", "").replace("http://", "").rstrip("/")
        return f"https://{self._bucket_name}.{host}/{key}"

    @property
    def is_local(self) -> bool:
        return False
