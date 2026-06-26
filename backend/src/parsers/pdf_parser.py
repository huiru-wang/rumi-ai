"""PDF parser with heading detection and page tracking using PyMuPDF."""

import logging
import re

import fitz

from src.parsers.base import DocumentSection

logger = logging.getLogger(__name__)

# Heuristic: text larger than body median by this factor is likely a heading
HEADING_FONT_RATIO = 1.15
MIN_HEADING_FONT_SIZE = 11.0


class PdfParser:
    """Extract structured sections from PDF files with page numbers."""

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
                "[PdfParser] extracted %d sections", len(sections),
            )
            return sections
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
                            }
                        )
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

    def _group_into_sections(
        self, blocks: list[dict], body_size: float
    ) -> list[dict]:
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
