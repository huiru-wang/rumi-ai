"""Shared application context bundling storage and service dependencies."""

import os
from dataclasses import dataclass

from src.managers.skill_manager import SkillManager
from src.storage.database import Database
from src.storage.file_store import FileStore
from src.storage.providers import LocalProvider, StorageProvider
from src.storage.vector_store import VectorStore


@dataclass
class AppContext:
    db: Database
    vector_store: VectorStore
    file_store: FileStore
    skill_manager: SkillManager

    @classmethod
    def from_env(cls) -> "AppContext":
        """Create an AppContext from environment variables."""
        data_dir = os.getenv("DATA_DIR", "./data")
        db = Database(f"{data_dir}/rumi_ai.db")
        provider = cls._create_storage_provider(data_dir)
        return cls(
            db=db,
            vector_store=VectorStore(
                host=os.getenv("CHROMA_HOST", "localhost"),
                port=int(os.getenv("CHROMA_PORT", "8001")),
            ),
            file_store=FileStore(f"{data_dir}/files", provider=provider, db=db),
            skill_manager=SkillManager(
                os.path.join(os.path.dirname(__file__), "../skills")
            ),
        )

    @staticmethod
    def _create_storage_provider(data_dir: str) -> StorageProvider:
        """Create a storage provider based on OSS_ENABLE env var."""
        if os.getenv("OSS_ENABLE", "false").lower() == "true":
            from src.storage.providers import OSSProvider

            return OSSProvider(
                endpoint=os.getenv("OSS_ENDPOINT", ""),
                bucket=os.getenv("OSS_BUCKET", ""),
                access_key_id=os.getenv("OSS_ACCESS_KEY_ID", ""),
                access_key_secret=os.getenv("OSS_ACCESS_KEY_SECRET", ""),
            )
        return LocalProvider(f"{data_dir}/files")
