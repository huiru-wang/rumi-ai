import hashlib
import logging
import os
from pathlib import Path

from langchain_openai import ChatOpenAI

from src.parsers import PdfParser, DocxParser, MarkdownParser
from src.parsers.base import DocumentSection, split_sections_into_chunks
from src.storage.database import Database
from src.storage.file_store import FileStore
from src.storage.vector_store import VectorStore

logger = logging.getLogger(__name__)


class DuplicateDocumentError(ValueError):
    """Raised when a duplicate document is detected during upload."""

    def __init__(self, message: str, existing_doc_id: str = ""):
        super().__init__(message)
        self.existing_doc_id = existing_doc_id


class DocManager:
    def __init__(
        self,
        db: Database,
        vector_store: VectorStore,
        file_store: FileStore,
    ):
        self.db = db
        self.vector_store = vector_store
        self.file_store = file_store
        self.llm = ChatOpenAI(
            model=os.getenv("SUMMARIZATION_MODEL"),
            api_key=os.getenv("SUMMARIZATION_API_KEY"),
            base_url=os.getenv("SUMMARIZATION_API_BASE"),
        )
        self._pdf_parser = PdfParser()
        self._docx_parser = DocxParser()
        self._markdown_parser = MarkdownParser()

    async def upload_document(
        self, workspace_id: str, filename: str, content: bytes
    ) -> dict:
        doc = await self.create_document_upload(workspace_id, filename, content)
        return await self.process_document(doc["id"])

    async def create_document_upload(
        self, workspace_id: str, filename: str, content: bytes
    ) -> dict:
        file_type = self._detect_type(filename)
        content_hash = hashlib.sha256(content).hexdigest()
        logger.info(
            "[DocManager] create_document_upload: filename=%s, type=%s, size=%d bytes, workspace=%s",
            filename,
            file_type,
            len(content),
            workspace_id,
        )

        # --- Duplicate detection: filename or content hash ---
        duplicate = await self.db.find_duplicate_document(
            workspace_id, filename, content_hash
        )
        if duplicate:
            if duplicate["filename"] == filename:
                raise DuplicateDocumentError(
                    f"文档 '{filename}' 已存在，请勿重复上传。如需更新请先删除旧文档。",
                    existing_doc_id=duplicate["id"],
                )
            else:
                raise DuplicateDocumentError(
                    f"与已有文档 '{duplicate['filename']}' 内容完全相同，无需重复上传。",
                    existing_doc_id=duplicate["id"],
                )

        storage_path = await self.file_store.save_doc(workspace_id, filename, content)
        logger.info("[DocManager] file saved to: %s", storage_path)
        doc = await self.db.create_document(
            workspace_id=workspace_id,
            filename=filename,
            file_type=file_type,
            storage_path=storage_path,
            content_hash=content_hash,
        )
        logger.info("[DocManager] document record created: id=%s", doc["id"])
        return doc

    async def process_document(self, doc_id: str) -> dict:
        doc = await self._get_document_by_id(doc_id)
        if not doc:
            raise ValueError(f"Document not found: {doc_id}")

        workspace_id = doc["workspace_id"]
        filename = doc["filename"]
        file_type = doc["file_type"]
        storage_path = doc["storage_path"]

        try:
            # --- Structured parsing ---
            await self.db.update_document(doc_id, status="parsing", error_message=None)
            content = await self.file_store.read(storage_path)
            sections = self._parse_structured(file_type, content)
            logger.info("[DocManager] parsed %d sections", len(sections))

            # Plain text for summary generation + debug export
            full_text = "\n\n".join(
                (f"## {s.title}\n{s.content}" if s.title else s.content)
                for s in sections
                if s.content.strip()
            )
            if not full_text.strip():
                raise ValueError(
                    "No extractable text found in document. "
                    "The file may be scanned or image-based and requires OCR."
                )

            md_filename = Path(filename).stem + ".md"
            md_content = f"# {filename}\n\n{full_text}"

            # If source is already markdown, reuse the same file (no duplicate)
            if file_type in ("markdown", "text"):
                logger.info(
                    "[DocManager] source is %s, skipping separate MD file", file_type
                )
            else:
                await self.file_store.save_doc(
                    workspace_id, md_filename, md_content.encode("utf-8")
                )
                logger.info(
                    "[DocManager] parsed text saved as: docs/%s", md_filename
                )
            await self.db.update_document(doc_id, status="parsed")

            # --- Section-aware chunking ---
            await self.db.update_document(doc_id, status="chunking")
            chunks = split_sections_into_chunks(sections)
            logger.info("[DocManager] split into %d chunks", len(chunks))

            await self.db.update_document(doc_id, status="indexing")
            self.vector_store.add_structured_chunks(
                workspace_id=workspace_id,
                doc_id=doc_id,
                chunks=chunks,
                filename=filename,
            )
            logger.info("[DocManager] chunks added to vector store")

            await self.db.update_document(doc_id, status="summarizing")
            summary = await self._generate_summary(full_text)
            logger.info(
                "[DocManager] summary generated: %s",
                summary[:100] if summary else "None",
            )
            await self.db.update_document(
                doc_id, status="ready", summary=summary, error_message=None
            )
            doc["status"] = "ready"
            doc["summary"] = summary
            doc["error_message"] = None
            logger.info("[DocManager] document ready: id=%s", doc["id"])
        except Exception as exc:
            logger.error(
                "[DocManager] upload failed for %s: %s", filename, exc, exc_info=True
            )
            await self.db.update_document(
                doc_id, status="error", error_message=str(exc)
            )
            doc["status"] = "error"
            doc["error_message"] = str(exc)
        return doc

    async def _get_document_by_id(self, doc_id: str) -> dict | None:
        if self.db.connection is None:
            await self.db.initialize()
        cursor = await self.db.connection.execute(
            "SELECT * FROM document WHERE id = ?", (doc_id,)
        )
        row = await cursor.fetchone()
        return dict(row) if row else None

    async def delete_workspace(self, workspace_id: str):
        """Delete all documents, vector store entries, and files for a workspace."""
        docs = await self.db.list_documents(workspace_id)
        for doc in docs:
            if doc.get("storage_path"):
                await self.file_store.delete_async(doc["storage_path"])
            self.vector_store.delete_by_doc_id(workspace_id, doc["id"])
            await self.db.delete_document(doc["id"], workspace_id)
        # Delete vector store collection
        self.vector_store.delete_workspace(workspace_id)
        # Delete file store directory (handles both local and OSS)
        await self.file_store.delete_workspace_async(workspace_id)

    async def delete_document(self, workspace_id: str, doc_id: str):
        docs = await self.db.list_documents(workspace_id)
        doc = next((d for d in docs if d["id"] == doc_id), None)
        if doc:
            if doc.get("storage_path"):
                await self.file_store.delete_async(doc["storage_path"])
                # Delete the parsed markdown file generated during processing
                md_path = Path(doc["storage_path"]).parent / (
                    Path(doc["filename"]).stem + ".md"
                )
                await self.file_store.delete_async(str(md_path))
            self.vector_store.delete_by_doc_id(workspace_id, doc_id)
            await self.db.delete_document(doc_id, workspace_id)

    # ------------------------------------------------------------------
    # Parsing
    # ------------------------------------------------------------------

    def _detect_type(self, filename: str) -> str:
        ext = Path(filename).suffix.lower()
        mapping = {
            ".pdf": "pdf",
            ".docx": "docx",
            ".doc": "docx",
            ".md": "markdown",
            ".txt": "text",
        }
        return mapping.get(ext, "unknown")

    def _parse_structured(
        self, file_type: str, content: bytes
    ) -> list[DocumentSection]:
        """Parse document into structured sections based on file type."""
        if file_type == "pdf":
            return self._pdf_parser.parse(content)
        elif file_type == "docx":
            return self._docx_parser.parse(content)
        elif file_type in ("markdown", "text"):
            text = content.decode("utf-8", errors="ignore")
            return self._markdown_parser.parse(text)
        else:
            text = content.decode("utf-8", errors="ignore")
            return self._markdown_parser.parse(text)

    # ------------------------------------------------------------------
    # Summary
    # ------------------------------------------------------------------

    async def _generate_summary(self, text: str) -> str:
        if not self.llm:
            return text[:500] + "..." if len(text) > 500 else text
        from langchain_core.messages import HumanMessage, SystemMessage

        try:
            messages = [
                SystemMessage(content="用一段话总结以下文档的核心内容，200字以内："),
                HumanMessage(content=text[:8000]),
            ]
            response = await self.llm.ainvoke(messages)
            return response.content
        except Exception as exc:
            logger.warning("[DocManager] LLM summary failed, using fallback: %s", exc)
            # 返回截断文本作为 fallback，不暴露 LLM 错误
            return text[:500] + "..." if len(text) > 500 else text
