import hashlib
import json
import logging
import math
import os
import re
from datetime import datetime
from pathlib import Path

from langchain_openai import ChatOpenAI

from src.parsers import PdfParser, DocxParser, MarkdownParser
from src.managers.vision_manager import VisionManager
from src.parsers.base import (
    DocumentBlock,
    DocumentSection,
    ParsedDocument,
    blocks_to_chunks,
)
from src.storage.database import Database
from src.storage.file_store import FileStore
from src.storage.vector_store import VectorStore

logger = logging.getLogger(__name__)

PROGRESS_STAGES = {
    "uploaded": ("等待解析", 0),
    "parsing": ("正在解析文档结构", 5),
    "parsed": ("文档结构解析完成", 60),
    "chunking": ("正在切分文档片段", 70),
    "indexing": ("正在写入知识库索引", 82),
    "summarizing": ("正在生成文档摘要", 92),
    "ready": ("解析完成", 100),
    "error": ("解析失败", 100),
}
PDF_ESTIMATE_SECONDS_PER_PAGE = 2.5
PDF_ESTIMATE_FIXED_SECONDS = 10
PDF_ESTIMATE_NOTE = "若文档包含较多图片或图表，解析时间可能增加"


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
        self._vision_manager = VisionManager(file_store=file_store)

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
        initial_progress = self._build_upload_progress(file_type, content)
        doc = await self.db.create_document(
            workspace_id=workspace_id,
            filename=filename,
            file_type=file_type,
            storage_path=storage_path,
            content_hash=content_hash,
            progress_data=initial_progress,
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
        existing_progress = self._parse_progress_data(doc.get("progress_data"))
        estimated_minutes = existing_progress.get("estimated_minutes")
        estimate_note = existing_progress.get("estimate_note", "")

        try:
            # --- Structured parsing ---
            await self._update_progress(
                doc_id,
                "parsing",
                message="正在读取文档并解析结构",
                current=0,
                total=0,
                estimated_minutes=estimated_minutes,
                estimate_note=estimate_note,
                extra_updates={"error_message": None},
            )
            content = await self.file_store.read(storage_path)
            logger.info(
                "[DocManager] parse start: doc_id=%s filename=%s type=%s",
                doc_id,
                filename,
                file_type,
            )
            parsed = await self._parse_structured(
                workspace_id=workspace_id,
                doc_id=doc_id,
                filename=filename,
                file_type=file_type,
                content=content,
                progress_doc_id=doc_id,
            )
            await self._update_progress(
                doc_id,
                "parsing",
                message="正在理解图片和图表内容",
                percent=56,
                estimated_minutes=estimated_minutes,
                estimate_note=estimate_note,
            )
            await self._enrich_blocks(parsed)
            block_counts: dict[str, int] = {}
            for block in parsed.blocks:
                block_counts[block.type] = block_counts.get(block.type, 0) + 1
            logger.info(
                "[DocManager] parse result: blocks=%d counts=%s",
                len(parsed.blocks),
                block_counts,
            )

            # Plain text for summary generation + debug export
            full_text = "\n\n".join(
                block.index_text() for block in parsed.blocks if block.index_text().strip()
            )
            if not full_text.strip():
                if parsed.blocks:
                    full_text = "文档已解析，但未提取到可索引文本。"
                else:
                    raise ValueError(
                        "No extractable text found in document. "
                        "The file may be scanned or image-based and requires OCR."
                    )

            md_filename = Path(filename).stem + ".md"
            md_content = parsed.to_markdown()
            parsed_filename = Path(filename).stem + ".parsed.json"
            parsed_json_content = json.dumps(parsed.to_dict(), ensure_ascii=False, indent=2)
            parsed_path = await self.file_store.save_doc(
                workspace_id,
                parsed_filename,
                parsed_json_content.encode("utf-8"),
            )
            logger.info("[DocManager] parsed json saved: path=%s", parsed_path)
            self._save_dev_parse_artifacts(
                doc_id=doc_id,
                filename=filename,
                parsed_json_content=parsed_json_content,
                markdown_content=md_content,
            )

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
            await self._update_progress(
                doc_id,
                "parsed",
                message=f"文档结构解析完成，共 {len(parsed.blocks)} 个内容块",
                estimated_minutes=estimated_minutes,
                estimate_note=estimate_note,
            )

            # --- Section-aware chunking ---
            await self._update_progress(
                doc_id,
                "chunking",
                message="正在切分文档片段",
                estimated_minutes=estimated_minutes,
                estimate_note=estimate_note,
            )
            chunks = blocks_to_chunks(parsed)
            chunk_counts: dict[str, int] = {}
            for chunk in chunks:
                key = chunk.block_type or "text"
                chunk_counts[key] = chunk_counts.get(key, 0) + 1
            logger.info(
                "[DocManager] chunking result: chunks=%d counts=%s",
                len(chunks),
                chunk_counts,
            )

            await self._update_progress(
                doc_id,
                "indexing",
                message=f"正在写入知识库索引，共 {len(chunks)} 个片段",
                estimated_minutes=estimated_minutes,
                estimate_note=estimate_note,
            )
            self.vector_store.add_structured_chunks(
                workspace_id=workspace_id,
                doc_id=doc_id,
                chunks=chunks,
                filename=filename,
            )
            logger.info("[DocManager] indexing done: doc_id=%s chunks=%d", doc_id, len(chunks))

            await self._update_progress(
                doc_id,
                "summarizing",
                message="正在生成文档摘要",
                estimated_minutes=estimated_minutes,
                estimate_note=estimate_note,
            )
            summary = await self._generate_summary(full_text)
            logger.info(
                "[DocManager] summary generated: %s",
                summary[:100] if summary else "None",
            )
            await self.db.update_document(
                doc_id,
                status="ready",
                summary=summary,
                error_message=None,
                progress_data=json.dumps(
                    self._build_progress(
                        "ready",
                        message="文档解析完成，可以开始问答和生成",
                    ),
                    ensure_ascii=False,
                ),
            )
            doc["status"] = "ready"
            doc["summary"] = summary
            doc["error_message"] = None
            logger.info("[DocManager] document ready: id=%s", doc["id"])
        except Exception as exc:
            logger.error(
                "[DocManager] upload failed for %s: %s", filename, exc, exc_info=True
            )
            await self._update_progress(
                doc_id,
                "error",
                message=str(exc),
                extra_updates={"error_message": str(exc)},
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

    def _build_progress(
        self,
        stage: str,
        *,
        message: str = "",
        percent: int | None = None,
        current: int = 0,
        total: int = 0,
        estimated_minutes: int | None = None,
        estimate_note: str = "",
    ) -> dict:
        stage_label, default_percent = PROGRESS_STAGES.get(stage, (stage, 0))
        progress = {
            "stage": stage,
            "stage_label": stage_label,
            "percent": max(0, min(100, percent if percent is not None else default_percent)),
            "message": message or stage_label,
            "current": max(0, current),
            "total": max(0, total),
            "updated_at": datetime.now().isoformat(),
        }
        if estimated_minutes is not None:
            progress["estimated_minutes"] = max(1, estimated_minutes)
        if estimate_note:
            progress["estimate_note"] = estimate_note
        return progress

    def _estimate_pdf_minutes(self, page_count: int) -> int:
        seconds = page_count * PDF_ESTIMATE_SECONDS_PER_PAGE + PDF_ESTIMATE_FIXED_SECONDS
        return max(1, math.ceil(seconds / 60))

    def _parse_progress_data(self, raw: object) -> dict:
        if isinstance(raw, dict):
            return raw
        if not raw:
            return {}
        try:
            data = json.loads(str(raw))
        except (json.JSONDecodeError, TypeError):
            return {}
        return data if isinstance(data, dict) else {}

    def _build_upload_progress(self, file_type: str, content: bytes) -> dict:
        total = 0
        estimated_minutes = None
        estimate_note = ""
        if file_type == "pdf":
            try:
                total = self._pdf_parser.page_count(content)
                if total > 0:
                    estimated_minutes = self._estimate_pdf_minutes(total)
                    estimate_note = PDF_ESTIMATE_NOTE
            except Exception as exc:
                logger.info("[DocManager] pdf estimate skipped: %s", exc)
        return self._build_progress(
            "uploaded",
            message="文档已上传，等待解析",
            current=0,
            total=total,
            estimated_minutes=estimated_minutes,
            estimate_note=estimate_note,
        )

    async def _update_progress(
        self,
        doc_id: str,
        stage: str,
        *,
        message: str = "",
        percent: int | None = None,
        current: int = 0,
        total: int = 0,
        extra_updates: dict | None = None,
        estimated_minutes: int | None = None,
        estimate_note: str = "",
    ) -> None:
        if estimated_minutes is None and total > 0:
            estimated_minutes = self._estimate_pdf_minutes(total)
            estimate_note = estimate_note or PDF_ESTIMATE_NOTE
        progress = self._build_progress(
            stage,
            message=message,
            percent=percent,
            current=current,
            total=total,
            estimated_minutes=estimated_minutes,
            estimate_note=estimate_note,
        )
        updates = {"status": stage, "progress_data": json.dumps(progress, ensure_ascii=False)}
        if extra_updates:
            updates.update(extra_updates)
        await self.db.update_document(doc_id, **updates)

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

    async def _parse_structured(
        self,
        workspace_id: str,
        doc_id: str,
        filename: str,
        file_type: str,
        content: bytes,
        progress_doc_id: str = "",
    ) -> ParsedDocument:
        """Parse document into block-first structured output."""
        async def save_asset(asset_filename: str, asset_content: bytes) -> str:
            asset_path = f"{Path(filename).stem}_assets/{asset_filename}"
            return await self.file_store.save_doc(workspace_id, asset_path, asset_content)

        async def report_pdf_page(current: int, total: int) -> None:
            percent = 5
            if total > 0:
                percent = 5 + int((current / total) * 50)
            await self._update_progress(
                progress_doc_id or doc_id,
                "parsing",
                message="正在解析 PDF 页面",
                percent=percent,
                current=current,
                total=total,
            )

        if file_type == "pdf":
            return await self._pdf_parser.parse_blocks(
                content,
                asset_saver=save_asset,
                filename=filename,
                progress_callback=report_pdf_page,
            )
        elif file_type == "docx":
            return await self._docx_parser.parse_blocks(
                content,
                asset_saver=save_asset,
                filename=filename,
            )
        elif file_type in ("markdown", "text"):
            text = content.decode("utf-8", errors="ignore")
            sections = self._markdown_parser.parse(text)
            return self._sections_to_parsed(filename, sections)
        else:
            text = content.decode("utf-8", errors="ignore")
            sections = self._markdown_parser.parse(text)
            return self._sections_to_parsed(filename, sections)

    def _save_dev_parse_artifacts(
        self,
        *,
        doc_id: str,
        filename: str,
        parsed_json_content: str,
        markdown_content: str,
    ) -> None:
        app_env = os.getenv("APP_ENV", "dev").strip().lower()
        if app_env not in {"dev", "local", "development", "test"}:
            return

        stem = Path(filename).stem or "document"
        safe_stem = re.sub(r'[\\/:*?"<>|]+', "_", stem).strip() or "document"
        repo_root = Path(__file__).resolve().parents[3]
        output_dir = repo_root / "tmp" / "doc_parse" / doc_id
        output_dir.mkdir(parents=True, exist_ok=True)

        parsed_path = output_dir / f"{safe_stem}.parsed.json"
        markdown_path = output_dir / f"{safe_stem}.md"
        parsed_path.write_text(parsed_json_content, encoding="utf-8")
        markdown_path.write_text(markdown_content, encoding="utf-8")
        logger.info(
            "[DocManager] dev parse artifacts saved: parsed_json=%s markdown=%s",
            parsed_path,
            markdown_path,
        )

    def _sections_to_parsed(
        self, filename: str, sections: list[DocumentSection]
    ) -> ParsedDocument:
        blocks: list[DocumentBlock] = []
        order = 0
        for section in sections:
            if section.title:
                blocks.append(
                    DocumentBlock(
                        id=f"legacy-{order}",
                        type="title",
                        text=section.title,
                        level=section.level,
                        page_start=section.page_start,
                        page_end=section.page_end,
                        parent_title=section.parent_title,
                        order=order,
                    )
                )
                order += 1
            if section.content:
                blocks.append(
                    DocumentBlock(
                        id=f"legacy-{order}",
                        type="paragraph",
                        text=section.content,
                        level=section.level,
                        page_start=section.page_start,
                        page_end=section.page_end,
                        parent_title=section.title or section.parent_title,
                        order=order,
                    )
                )
                order += 1
        return ParsedDocument(title=filename, blocks=blocks)

    async def _enrich_blocks(self, parsed: ParsedDocument) -> None:
        image_total = 0
        image_ok = 0
        image_failed = 0
        table_total = 0
        logger.info("[DocManager] enrichment start")
        for block in parsed.blocks:
            if block.type in ("image", "chart"):
                image_total += 1
                before = block.summary
                await self._vision_manager.enrich_block(block)
                if block.summary and block.summary != before:
                    image_ok += 1
                else:
                    image_failed += 1
            elif block.type == "table":
                table_total += 1
                if not block.summary:
                    block.summary = self._fallback_table_summary(block.text)
        logger.info(
            "[DocManager] enrichment done: images=%d images_ok=%d images_failed=%d tables=%d",
            image_total,
            image_ok,
            image_failed,
            table_total,
        )

    def _fallback_table_summary(self, text: str) -> str:
        lines = [line for line in text.splitlines() if line.strip()]
        return f"表格包含 {max(len(lines) - 2, 0)} 行数据。" if lines else ""

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
