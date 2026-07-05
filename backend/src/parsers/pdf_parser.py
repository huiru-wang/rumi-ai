"""PDF parser with heading detection and page tracking using PyMuPDF."""

import logging
import re
from typing import Awaitable, Callable

import fitz

from src.parsers.base import DocumentAsset, DocumentBlock, DocumentSection, ParsedDocument

logger = logging.getLogger(__name__)

# Heuristic: text larger than body median by this factor is likely a heading
HEADING_FONT_RATIO = 1.15
MIN_HEADING_FONT_SIZE = 11.0


class PdfParser:
    """Extract structured sections from PDF files with page numbers."""

    def page_count(self, source: str | bytes) -> int:
        """Return PDF page count without running full parsing."""
        if isinstance(source, bytes):
            doc = fitz.open(stream=source, filetype="pdf")
        else:
            doc = fitz.open(source)
        try:
            return int(doc.page_count)
        finally:
            doc.close()

    def parse(self, source: str | bytes) -> list[DocumentSection]:
        """Parse a PDF file.

        Args:
            source: either a filesystem path (str) or raw PDF bytes.
        """
        if isinstance(source, bytes):
            doc = fitz.open(stream=source, filetype="pdf")
        else:
            doc = fitz.open(source)
        try:
            blocks = self._extract_blocks(doc)
            if not blocks:
                return self._fallback_by_page(doc)

            body_size = self._detect_body_font_size(blocks)
            raw_sections = self._group_into_sections(blocks, body_size)
            sections = self._assign_hierarchy(raw_sections)
            logger.info(
                "[PdfParser] extracted %d sections",
                len(sections),
            )
            return sections
        finally:
            doc.close()

    async def parse_blocks(
        self,
        source: str | bytes,
        asset_saver: Callable[[str, bytes], Awaitable[str]] | None = None,
        filename: str = "document.pdf",
        progress_callback: Callable[[int, int], Awaitable[None]] | None = None,
    ) -> ParsedDocument:
        """Parse PDF into reading-order blocks and extracted image assets."""
        if isinstance(source, bytes):
            doc = fitz.open(stream=source, filetype="pdf")
        else:
            doc = fitz.open(source)
        try:
            logger.info(
                "[PdfParser] start parse_blocks: filename=%s pages=%d", filename, doc.page_count
            )
            text_blocks = await self._extract_blocks_with_progress(doc, progress_callback)
            body_size = self._detect_body_font_size(text_blocks)
            logger.info("[PdfParser] body font detected: size=%s", body_size)
            blocks: list[DocumentBlock] = []
            assets: list[DocumentAsset] = []
            active_title = ""
            order = 0
            image_count = 0

            for block in text_blocks:
                is_heading = self._is_heading(block, body_size)
                block_type = "title" if is_heading else "paragraph"
                level = self._heading_level(block, body_size) if is_heading else 0
                if is_heading:
                    active_title = block["text"]
                blocks.append(
                    DocumentBlock(
                        id=f"pdf-{order}",
                        type=block_type,
                        text=block["text"],
                        level=level,
                        page_start=block["page"],
                        page_end=block["page"],
                        bbox=block.get("bbox"),
                        parent_title="" if is_heading else active_title,
                        order=order,
                    )
                )
                order += 1

            seen_xrefs: set[int] = set()
            for page_num, page in enumerate(doc, start=1):
                page_image_count = 0
                for image in page.get_images(full=True):
                    xref = image[0]
                    if xref in seen_xrefs:
                        continue
                    seen_xrefs.add(xref)
                    try:
                        extracted = doc.extract_image(xref)
                        image_bytes = extracted.get("image", b"")
                        ext = extracted.get("ext", "png")
                        asset_path = ""
                        if asset_saver and image_bytes:
                            asset_path = await asset_saver(f"image_{order:04d}.{ext}", image_bytes)
                        block = DocumentBlock(
                            id=f"pdf-{order}",
                            type="image",
                            page_start=page_num,
                            page_end=page_num,
                            parent_title=active_title,
                            asset_path=asset_path,
                            order=order,
                        )
                        blocks.append(block)
                        if asset_path:
                            assets.append(
                                DocumentAsset(
                                    id=block.id,
                                    type=block.type,
                                    path=asset_path,
                                    filename=f"image_{order:04d}.{ext}",
                                    page=page_num,
                                )
                            )
                        logger.info(
                            "[PdfParser] image extracted: page=%d xref=%d size=%d path=%s",
                            page_num,
                            xref,
                            len(image_bytes),
                            asset_path,
                        )
                        order += 1
                        image_count += 1
                        page_image_count += 1
                    except Exception as exc:
                        logger.warning(
                            "[PdfParser] image extraction failed: page=%d xref=%d error=%s",
                            page_num,
                            xref,
                            exc,
                        )
                if progress_callback:
                    await progress_callback(page_num, doc.page_count)
                if hasattr(page, "find_tables"):
                    try:
                        table_result = page.find_tables()
                        table_count = len(getattr(table_result, "tables", []) or [])
                        if table_count:
                            logger.info(
                                "[PdfParser] table extraction detected but skipped in MVP: page=%d tables=%d",
                                page_num,
                                table_count,
                            )
                    except Exception as exc:
                        logger.info(
                            "[PdfParser] table extraction skipped/failed: page=%d reason=%s",
                            page_num,
                            exc,
                        )

            logger.info(
                "[PdfParser] done: blocks=%d images=%d tables=%d",
                len(blocks),
                image_count,
                0,
            )
            return ParsedDocument(title=filename, blocks=blocks, assets=assets)
        finally:
            doc.close()

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _extract_blocks(self, doc: fitz.Document) -> list[dict]:
        """Extract text spans with font info and page numbers."""
        blocks = []
        for page_num, page in enumerate(doc, start=1):
            text_dict = page.get_text("dict", flags=fitz.TEXT_PRESERVE_WHITESPACE)
            for block in text_dict.get("blocks", []):
                if block.get("type") != 0:  # text block only
                    continue
                for line in block.get("lines", []):
                    line_text = ""
                    max_size = 0.0
                    is_bold = False
                    for span in line.get("spans", []):
                        line_text += span.get("text", "")
                        size = span.get("size", 0)
                        if size > max_size:
                            max_size = size
                        if "bold" in span.get("font", "").lower():
                            is_bold = True
                    line_text = line_text.strip()
                    if line_text:
                        blocks.append(
                            {
                                "text": line_text,
                                "size": max_size,
                                "bold": is_bold,
                                "page": page_num,
                                "bbox": [float(v) for v in line.get("bbox", [])],
                            }
                        )
        return blocks

    async def _extract_blocks_with_progress(
        self,
        doc: fitz.Document,
        progress_callback: Callable[[int, int], Awaitable[None]] | None = None,
    ) -> list[dict]:
        """Extract text spans and report page-level progress for async parsing."""
        blocks = []
        for page_num, page in enumerate(doc, start=1):
            text_dict = page.get_text("dict", flags=fitz.TEXT_PRESERVE_WHITESPACE)
            for block in text_dict.get("blocks", []):
                if block.get("type") != 0:
                    continue
                for line in block.get("lines", []):
                    line_text = ""
                    max_size = 0.0
                    is_bold = False
                    for span in line.get("spans", []):
                        line_text += span.get("text", "")
                        size = span.get("size", 0)
                        if size > max_size:
                            max_size = size
                        if "bold" in span.get("font", "").lower():
                            is_bold = True
                    line_text = line_text.strip()
                    if line_text:
                        blocks.append(
                            {
                                "text": line_text,
                                "size": max_size,
                                "bold": is_bold,
                                "page": page_num,
                                "bbox": [float(v) for v in line.get("bbox", [])],
                            }
                        )
            if progress_callback:
                await progress_callback(page_num, doc.page_count)
        return blocks

    def _detect_body_font_size(self, blocks: list[dict]) -> float:
        """Find the most common font size (= body text)."""
        size_counts: dict[float, int] = {}
        for block in blocks:
            rounded = round(block["size"], 1)
            size_counts[rounded] = size_counts.get(rounded, 0) + len(block["text"])
        if not size_counts:
            return 10.0
        return max(size_counts, key=size_counts.get)

    def _is_heading(self, block: dict, body_size: float) -> bool:
        """Heuristic: heading if larger font or bold + matches heading patterns."""
        text = block["text"]
        size = block["size"]

        # Too long to be a heading
        if len(text) > 120:
            return False

        # Font size significantly larger than body
        if size >= body_size * HEADING_FONT_RATIO and size >= MIN_HEADING_FONT_SIZE:
            return True

        # Bold + matches common heading patterns (numbered headings, Chinese chapter markers)
        if block["bold"] and re.match(
            r"^(\d+[\.\、]|[一二三四五六七八九十]+[\.\、、]|第[一二三四五六七八九十\d]+[章节篇]|附录)",
            text,
        ):
            return True

        return False

    def _heading_level(self, block: dict, body_size: float) -> int:
        """Estimate heading level from font size relative to body."""
        ratio = block["size"] / body_size if body_size > 0 else 1.0
        if ratio >= 1.6:
            return 1
        if ratio >= 1.3:
            return 2
        return 3

    def _group_into_sections(self, blocks: list[dict], body_size: float) -> list[dict]:
        """Group consecutive blocks under heading blocks."""
        sections: list[dict] = []
        current: dict | None = None

        for block in blocks:
            if self._is_heading(block, body_size):
                if current:
                    sections.append(current)
                current = {
                    "title": block["text"],
                    "level": self._heading_level(block, body_size),
                    "lines": [],
                    "page_start": block["page"],
                    "page_end": block["page"],
                }
            else:
                if current is None:
                    current = {
                        "title": "",
                        "level": 0,
                        "lines": [],
                        "page_start": block["page"],
                        "page_end": block["page"],
                    }
                current["lines"].append(block["text"])
                current["page_end"] = block["page"]

        if current:
            sections.append(current)

        return sections

    def _assign_hierarchy(self, raw_sections: list[dict]) -> list[DocumentSection]:
        """Assign parent_title based on heading levels."""
        result: list[DocumentSection] = []
        chapter_title = ""

        for section in raw_sections:
            level = section["level"]
            title = section["title"]

            if level == 1:
                chapter_title = title
            elif level == 0:
                # Content before first heading
                pass

            result.append(
                DocumentSection(
                    title=title,
                    level=max(level, 1),
                    content="\n".join(section["lines"]),
                    page_start=section["page_start"],
                    page_end=section["page_end"],
                    parent_title=chapter_title if level > 1 else "",
                )
            )

        return result

    def _fallback_by_page(self, doc: fitz.Document) -> list[DocumentSection]:
        """Fallback: treat each page as a section when structure detection fails."""
        sections = []
        for page_num, page in enumerate(doc, start=1):
            text = page.get_text().strip()
            if text:
                sections.append(
                    DocumentSection(
                        title=f"第{page_num}页",
                        level=1,
                        content=text,
                        page_start=page_num,
                        page_end=page_num,
                    )
                )
        return sections
