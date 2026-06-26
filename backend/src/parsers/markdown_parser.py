"""Markdown parser using heading markers (#, ##, ###)."""

import logging
import re

from src.parsers.base import DocumentSection

logger = logging.getLogger(__name__)

HEADING_RE = re.compile(r"^(#{1,4})\s+(.+)$", re.MULTILINE)


class MarkdownParser:
    """Extract structured sections from Markdown text."""

    def parse(self, text: str) -> list[DocumentSection]:
        sections: list[DocumentSection] = []
        chapter_title = ""

        # Find all headings with their positions
        headings = list(HEADING_RE.finditer(text))

        if not headings:
            # No headings — return entire text as one section
            stripped = text.strip()
            if stripped:
                sections.append(
                    DocumentSection(title="", level=1, content=stripped)
                )
            return sections

        # Content before first heading
        preamble = text[: headings[0].start()].strip()
        if preamble:
            sections.append(
                DocumentSection(title="", level=1, content=preamble)
            )

        for i, match in enumerate(headings):
            level = len(match.group(1))  # number of # chars
            title = match.group(2).strip()

            # Content = text between this heading and the next (or end)
            content_start = match.end()
            content_end = headings[i + 1].start() if i + 1 < len(headings) else len(text)
            content = text[content_start:content_end].strip()

            if level == 1:
                chapter_title = title

            sections.append(
                DocumentSection(
                    title=title,
                    level=min(level, 3),
                    content=content,
                    parent_title=chapter_title if level > 1 else "",
                )
            )

        logger.info("[MarkdownParser] extracted %d sections", len(sections))
        return sections
