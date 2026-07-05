import logging

from langchain.tools import tool, ToolRuntime

from src.agent.state import MainAgentState
from src.storage.vector_store import VectorStore
from pathlib import PurePosixPath

from src.url_utils import build_document_asset_url

logger = logging.getLogger(__name__)


def _format_location(result: dict) -> str:
    """Build a human-readable location string like '五、MySQL数据库 > 5.3 SQL语句 (p.38)'."""
    parts: list[str] = []

    chapter = result.get("chapter_title", "")
    section = result.get("section_title", "")

    if chapter and section and chapter != section:
        parts.append(f"{chapter} > {section}")
    elif section:
        parts.append(section)
    elif chapter:
        parts.append(chapter)

    page_start = result.get("page_start", 0)
    page_end = result.get("page_end", 0)
    if page_start > 0:
        if page_end > page_start:
            parts.append(f"p.{page_start}-{page_end}")
        else:
            parts.append(f"p.{page_start}")

    if not parts:
        chunk_idx = result.get("chunk_index", 0)
        parts.append(f"第{chunk_idx + 1}段")

    return " | ".join(parts)


def _format_page(result: dict) -> str:
    page_start = result.get("page_start", 0)
    page_end = result.get("page_end", 0)
    if page_start > 0:
        if page_end > page_start:
            return f"第{page_start}-{page_end}页"
        return f"第{page_start}页"
    return "-"


def _format_ref_marker(result: dict) -> str:
    """Build the citation marker copied by the LLM: [ref:文档名|页码|一级标题|二级标题]."""
    filename = result.get("filename", "unknown")
    page = _format_page(result)
    chapter = (result.get("chapter_title", "") or "").strip()
    section = (result.get("section_title", "") or "").strip()

    parts = [filename, page]
    if chapter:
        parts.append(chapter)
    if section and section != chapter:
        parts.append(section)
    return f"[ref:{'|'.join(parts)}]"


def _format_result(index: int, result: dict) -> str:
    filename = result.get("filename", "unknown")
    location = _format_location(result)
    ref_marker = _format_ref_marker(result)
    block_type = result.get("block_type", "") or "text"
    text = result.get("text", "")
    caption = result.get("caption", "")
    asset_path = result.get("asset_path", "")
    doc_id = result.get("doc_id", "")

    header = f"[片段{index + 1}] 📄 {filename} | {location}\n来源索引：{ref_marker}"
    if block_type in ("image", "chart") and asset_path and doc_id:
        alt = caption or "文档图片"
        asset_filename = PurePosixPath(asset_path).name
        url = build_document_asset_url(doc_id, asset_filename)
        logger.info(
            "[Tool:rag_search] public url built: asset_path=%s url=%s",
            asset_path,
            url,
        )
        image_markdown = f"![{alt}]({url})"
        return (
            f"{header}\n{text}\n\n"
            "可直接用于最终回答的图片 Markdown（若与用户问题相关，请原样保留）：\n"
            f"{image_markdown}"
        )
    if block_type == "table":
        label = caption or "文档表格"
        return f"{header}\n表格片段：{label}\n{text}"
    return f"{header}\n{text}"


def create_rag_search_tool(vector_store: VectorStore):
    @tool
    def rag_search(runtime: ToolRuntime[MainAgentState], query: str, top_k: int = 5, doc_id: str = "", **kwargs) -> str:
        """从当前工作区的知识库中检索相关文档片段。当用户提出与文档内容相关的问题时使用。

        当用户明确指定了某篇文档时，使用 doc_id 参数限定检索范围，只在该文档内检索。
        文档的 doc_id 可在系统提示的「当前知识库文档摘要」中找到。
        不传 doc_id 则在当前工作区所有文档中检索。
        """
        workspace_id = runtime.state.get("workspace_id", "default")
        effective_doc_id = doc_id.strip() or None
        logger.info(
            "[Tool:rag_search] query='%s', top_k=%d, doc_id=%s, workspace=%s",
            query[:80], top_k, effective_doc_id, workspace_id,
        )
        try:
            results = vector_store.search(
                workspace_id=workspace_id, query=query, top_k=top_k, doc_id=effective_doc_id
            )
        except Exception as exc:
            logger.error("[Tool:rag_search] search failed: %s", exc, exc_info=True)
            return f"知识库检索失败: {exc}"
        if not results:
            logger.info("[Tool:rag_search] no results found")
            return "未找到相关文档内容。"
        output = []
        for i, result in enumerate(results):
            logger.info(
                "[Tool:rag_search] hit: rank=%d type=%s asset_path=%s",
                i + 1,
                result.get("block_type", ""),
                result.get("asset_path", ""),
            )
            output.append(_format_result(i, result))
        logger.info("[Tool:rag_search] returned %d results", len(results))
        return "\n\n".join(output)

    return rag_search
