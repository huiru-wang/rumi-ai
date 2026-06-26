"""Dependency injection for API routes."""

from dotenv import load_dotenv

from src.app_context import AppContext
from src.managers.doc_manager import DocManager
from src.managers.style_extract_manager import StyleExtractManager

load_dotenv()

app_ctx = AppContext.from_env()

# Backward-compatible aliases
db = app_ctx.db
vector_store = app_ctx.vector_store
file_store = app_ctx.file_store
skill_manager = app_ctx.skill_manager

doc_service = DocManager(
    db=db, vector_store=vector_store, file_store=file_store
)

style_extract_manager = StyleExtractManager(db=db, file_store=file_store)
