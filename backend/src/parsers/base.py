"""Base data structures for structured document parsing."""

import json
from dataclasses import asdict, dataclass, field


@dataclass
class DocumentSection:
    """A structural unit extracted from a document (chapter, section, or subsection)."""

    title: str
    level: int  # 1=chapter, 2=section, 3=subsection
    content: str
    page_start: int = 0
    page_end: int = 0
    parent_title: str = ""


@dataclass
class DocumentAsset:
    """A saved non-text asset extracted from a document."""

    id: str
    type: str  # image, chart
    path: str
    filename: str
    mime_type: str = ""
    page: int = 0
    bbox: list[float] | None = None


@dataclass
class DocumentBlock:
    """A reading-order content block extracted from a document."""

    id: str
    type: str  # title, paragraph, list, table, image, chart
    text: str = ""
    level: int = 0
    page_start: int = 0
    page_end: int = 0
    bbox: list[float] | None = None
    parent_title: str = ""
    caption: str = ""
    asset_path: str = ""
    html: str = ""
    summary: str = ""
    order: int = 0

    def index_text(self) -> str:
        """Return text optimized for embedding and RAG display."""
        parts: list[str] = []
        if self.type in ("image", "chart"):
            label = self.caption or "文档图片"
            parts.append(f"图片：{label}")
            if self.parent_title:
                parts.append(f"所属章节：{self.parent_title}")
            if self.summary:
                parts.append(f"图片说明：{self.summary}")
            elif self.text:
                parts.append(self.text)
            return "\n".join(part for part in parts if part.strip())

        if self.type == "table":
            label = self.caption or "文档表格"
            parts.append(f"表格：{label}")
            if self.parent_title:
                parts.append(f"所属章节：{self.parent_title}")
            if self.summary:
                parts.append(f"表格说明：{self.summary}")
            if self.text:
                parts.append(self.text)
            return "\n".join(part for part in parts if part.strip())

        if self.text:
            parts.append(self.text)
        return "\n".join(part for part in parts if part.strip())

    def to_section(self) -> DocumentSection:
        """Convert to the legacy section shape used by older callers."""
        return DocumentSection(
            title=self.text if self.type == "title" else self.parent_title,
            level=self.level or 1,
            content=self.index_text(),
            page_start=self.page_start,
            page_end=self.page_end,
            parent_title=self.parent_title,
        )


@dataclass
class ParsedDocument:
    """Structured document result in reading order."""

    title: str
    blocks: list[DocumentBlock]
    assets: list[DocumentAsset] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "title": self.title,
            "blocks": [asdict(block) for block in self.blocks],
            "assets": [asdict(asset) for asset in self.assets],
        }

    def to_markdown(self) -> str:
        lines = [f"# {self.title}", ""]
        for block in self.blocks:
            if block.type == "title":
                level = min(max(block.level or 1, 1), 6)
                lines.extend([f"{'#' * level} {block.text}", ""])
            elif block.type == "table":
                if block.caption:
                    lines.extend([f"**{block.caption}**", ""])
                if block.summary:
                    lines.extend([block.summary, ""])
                if block.text:
                    lines.extend([block.text, ""])
            elif block.type in ("image", "chart"):
                label = block.caption or "图片"
                if block.summary:
                    lines.extend([f"![{label}]({block.asset_path})", "", block.summary, ""])
                elif block.asset_path:
                    lines.extend([f"![{label}]({block.asset_path})", ""])
            elif block.text:
                lines.extend([block.text, ""])
        return "\n".join(lines).strip() + "\n"


@dataclass
class ChunkWithMetadata:
    """A text chunk ready for vector storage, enriched with structural metadata."""

    text: str
    section_title: str = ""
    chapter_title: str = ""
    page_start: int = 0
    page_end: int = 0
    section_level: int = 0
    chunk_index: int = 0
    block_id: str = ""
    block_type: str = ""
    asset_path: str = ""
    caption: str = ""
    bbox: list[float] | None = None
    content_kind: str = "text"

    def to_metadata(self, doc_id: str, filename: str) -> dict:
        """Convert to ChromaDB metadata dict."""
        return {
            "doc_id": doc_id,
            "filename": filename,
            "chunk_index": self.chunk_index,
            "section_title": self.section_title,
            "chapter_title": self.chapter_title,
            "page_start": self.page_start,
            "page_end": self.page_end,
            "section_level": self.section_level,
            "block_id": self.block_id,
            "block_type": self.block_type,
            "asset_path": self.asset_path,
            "caption": self.caption,
            "bbox": json.dumps(self.bbox or [], ensure_ascii=False),
            "content_kind": self.content_kind,
        }


MAX_CHUNK_SIZE = 2000


def split_sections_into_chunks(
    sections: list[DocumentSection],
) -> list[ChunkWithMetadata]:
    """Convert parsed sections into chunks, splitting oversized sections by paragraphs."""
    from langchain_text_splitters import RecursiveCharacterTextSplitter

    splitter = RecursiveCharacterTextSplitter(
        chunk_size=MAX_CHUNK_SIZE,
        chunk_overlap=200,
        separators=["\n\n", "\n", "。", "；", " "],
    )

    chunks: list[ChunkWithMetadata] = []
    index = 0

    for section in sections:
        content = section.content.strip()
        if not content:
            continue

        if len(content) <= MAX_CHUNK_SIZE:
            chunks.append(
                ChunkWithMetadata(
                    text=content,
                    section_title=section.title,
                    chapter_title=section.parent_title,
                    page_start=section.page_start,
                    page_end=section.page_end,
                    section_level=section.level,
                    chunk_index=index,
                )
            )
            index += 1
        else:
            sub_chunks = splitter.split_text(content)
            for sub in sub_chunks:
                chunks.append(
                    ChunkWithMetadata(
                        text=sub,
                        section_title=section.title,
                        chapter_title=section.parent_title,
                        page_start=section.page_start,
                        page_end=section.page_end,
                        section_level=section.level,
                        chunk_index=index,
                    )
                )
                index += 1

    return chunks


def blocks_to_sections(parsed: ParsedDocument) -> list[DocumentSection]:
    """Convert block-first parsed output into legacy sections."""
    sections: list[DocumentSection] = []
    current_title = ""
    current_level = 1
    current_lines: list[str] = []
    page_start = 0
    page_end = 0

    def flush():
        nonlocal current_lines, page_start, page_end
        if not current_lines:
            return
        sections.append(
            DocumentSection(
                title=current_title,
                level=current_level,
                content="\n".join(current_lines),
                page_start=page_start,
                page_end=page_end,
                parent_title=current_title,
            )
        )
        current_lines = []
        page_start = 0
        page_end = 0

    for block in parsed.blocks:
        if block.type == "title":
            flush()
            current_title = block.text
            current_level = block.level or 1
            continue
        text = block.index_text().strip()
        if not text:
            continue
        if page_start == 0:
            page_start = block.page_start
        page_end = block.page_end or block.page_start or page_end
        current_lines.append(text)

    flush()
    if not sections:
        body = "\n\n".join(block.index_text() for block in parsed.blocks if block.index_text().strip())
        if body.strip():
            sections.append(DocumentSection(title="", level=1, content=body))
    return sections


def blocks_to_chunks(parsed: ParsedDocument) -> list[ChunkWithMetadata]:
    """Convert reading-order blocks into vector chunks with block metadata."""
    from langchain_text_splitters import RecursiveCharacterTextSplitter

    splitter = RecursiveCharacterTextSplitter(
        chunk_size=MAX_CHUNK_SIZE,
        chunk_overlap=200,
        separators=["\n\n", "\n", "。", "；", " "],
    )
    chunks: list[ChunkWithMetadata] = []
    index = 0
    active_h1 = ""
    active_h2 = ""
    active_level = 1

    for block in parsed.blocks:
        if block.type == "title":
            level = block.level or 1
            if level <= 1:
                active_h1 = block.text
                active_h2 = ""
                active_level = 1
            elif level == 2:
                active_h2 = block.text
                active_level = 2
            else:
                active_level = level
            continue

        text = block.index_text().strip()
        if not text:
            continue

        if len(text) <= MAX_CHUNK_SIZE:
            pieces = [text]
        else:
            pieces = splitter.split_text(text)

        for piece in pieces:
            section_title = active_h2 or block.parent_title
            chapter_title = active_h1
            if not chapter_title and not active_h2:
                chapter_title = block.parent_title
            chunks.append(
                ChunkWithMetadata(
                    text=piece,
                    section_title=section_title,
                    chapter_title=chapter_title,
                    page_start=block.page_start,
                    page_end=block.page_end or block.page_start,
                    section_level=active_level,
                    chunk_index=index,
                    block_id=block.id,
                    block_type=block.type,
                    asset_path=block.asset_path,
                    caption=block.caption,
                    bbox=block.bbox,
                    content_kind=block.type,
                )
            )
            index += 1

    return chunks
