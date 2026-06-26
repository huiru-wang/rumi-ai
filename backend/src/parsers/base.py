"""Base data structures for structured document parsing."""

from dataclasses import dataclass, field


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
class ChunkWithMetadata:
    """A text chunk ready for vector storage, enriched with structural metadata."""

    text: str
    section_title: str = ""
    chapter_title: str = ""
    page_start: int = 0
    page_end: int = 0
    section_level: int = 0
    chunk_index: int = 0

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
