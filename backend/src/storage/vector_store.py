import logging
import os
import uuid

import chromadb
import dashscope
from chromadb.errors import NotFoundError
from chromadb.api.types import Documents, EmbeddingFunction, Embeddings

logger = logging.getLogger(__name__)


class DashscopeEmbeddingFunction(EmbeddingFunction):
    """ChromaDB embedding function using Dashscope text-embedding-v2."""

    def __init__(self):
        pass

    def __call__(self, input: Documents) -> Embeddings:
        response = dashscope.TextEmbedding.call(
            model=os.getenv("EMBEDDING_MODEL", "text-embedding-v2"),
            api_key=os.getenv("EMBEDDING_API_KEY"),
            base_url=os.getenv("EMBEDDING_API_BASE"),
            input=input,
        )
        if response.status_code != 200:
            logger.error(
                "[Embedding] Dashscope error: status=%s, message=%s",
                response.status_code,
                getattr(response, "message", "unknown"),
            )
            raise RuntimeError(
                f"Dashscope embedding failed: {response.status_code} {getattr(response, 'message', '')}"
            )
        logger.info("[Embedding] success, got %d embeddings", len(response.output["embeddings"]))
        return [item["embedding"] for item in response.output["embeddings"]]


class VectorStore:
    """Vector store backed by a ChromaDB HTTP server.

    Both FastAPI and LangGraph processes share the same server via HTTP,
    eliminating the SQLite file-locking and Rust FFI lifetime issues that
    plagued the PersistentClient approach.
    """

    def __init__(self, host: str, port: int, embedding_fn: EmbeddingFunction = None):
        self._host = host
        self._port = port
        self._embedding_fn = embedding_fn or DashscopeEmbeddingFunction()
        self._client = chromadb.HttpClient(host=host, port=port)
        logger.info("[VectorStore] connected to ChromaDB server at %s:%s", host, port)

    def _get_collection(self, workspace_id: str):
        return self._client.get_or_create_collection(
            name=f"ws_{workspace_id}",
            metadata={"hnsw:space": "cosine"},
            embedding_function=self._embedding_fn,
        )

    def _get_existing_collection(self, workspace_id: str):
        return self._client.get_collection(
            name=f"ws_{workspace_id}",
            embedding_function=self._embedding_fn,
        )

    def add_chunks(
        self,
        workspace_id: str,
        doc_id: str,
        chunks: list[str],
        filename: str = "",
        batch_size: int = 20,
    ):
        """Legacy: add plain text chunks (kept for backward compatibility)."""
        logger.info(
            "[VectorStore] add_chunks: workspace=%s, doc=%s, filename=%s, %d chunks (batch_size=%d)",
            workspace_id,
            doc_id,
            filename,
            len(chunks),
            batch_size,
        )
        collection = self._get_collection(workspace_id)
        for start in range(0, len(chunks), batch_size):
            batch = chunks[start : start + batch_size]
            batch_ids = [str(uuid.uuid4()) for _ in batch]
            batch_metas = [
                {"doc_id": doc_id, "filename": filename, "chunk_index": start + j}
                for j in range(len(batch))
            ]
            logger.info(
                "[VectorStore] adding batch %d-%d / %d",
                start + 1,
                start + len(batch),
                len(chunks),
            )
            collection.add(documents=batch, ids=batch_ids, metadatas=batch_metas)
        logger.info("[VectorStore] add_chunks done")

    def add_structured_chunks(
        self,
        workspace_id: str,
        doc_id: str,
        chunks: list,
        filename: str = "",
        batch_size: int = 20,
    ):
        """Add ChunkWithMetadata objects with section/page metadata."""
        from src.parsers.base import ChunkWithMetadata

        logger.info(
            "[VectorStore] add_structured_chunks: workspace=%s, doc=%s, filename=%s, %d chunks",
            workspace_id,
            doc_id,
            filename,
            len(chunks),
        )
        collection = self._get_collection(workspace_id)
        for start in range(0, len(chunks), batch_size):
            batch: list[ChunkWithMetadata] = chunks[start : start + batch_size]
            batch_ids = [str(uuid.uuid4()) for _ in batch]
            batch_docs = [chunk.text for chunk in batch]
            batch_metas = [chunk.to_metadata(doc_id, filename) for chunk in batch]
            logger.info(
                "[VectorStore] adding batch %d-%d / %d",
                start + 1,
                start + len(batch),
                len(chunks),
            )
            collection.add(documents=batch_docs, ids=batch_ids, metadatas=batch_metas)
        logger.info("[VectorStore] add_structured_chunks done")

    def search(
        self,
        workspace_id: str,
        query: str,
        top_k: int = 5,
        doc_id: str | None = None,
    ) -> list[dict]:
        logger.info(
            "[VectorStore] search: workspace=%s, query='%s', top_k=%d, doc_id=%s",
            workspace_id,
            query[:80],
            top_k,
            doc_id,
        )
        try:
            collection = self._get_existing_collection(workspace_id)
        except NotFoundError:
            logger.info("[VectorStore] collection not found for workspace=%s", workspace_id)
            return []
        where = {"doc_id": doc_id} if doc_id else None
        results = collection.query(query_texts=[query], n_results=top_k, where=where)
        output = []
        for i, doc_text in enumerate(results["documents"][0]):
            meta = results["metadatas"][0][i]
            output.append(
                {
                    "text": doc_text,
                    "doc_id": meta.get("doc_id", ""),
                    "filename": meta.get("filename", "unknown"),
                    "chunk_index": meta.get("chunk_index", i),
                    "section_title": meta.get("section_title", ""),
                    "chapter_title": meta.get("chapter_title", ""),
                    "page_start": meta.get("page_start", 0),
                    "page_end": meta.get("page_end", 0),
                    "section_level": meta.get("section_level", 0),
                    "distance": (results["distances"][0][i] if results.get("distances") else None),
                }
            )
        logger.info("[VectorStore] search returned %d results", len(output))
        return output

    def delete_by_doc_id(self, workspace_id: str, doc_id: str):
        try:
            collection = self._get_existing_collection(workspace_id)
        except NotFoundError:
            return
        collection.delete(where={"doc_id": doc_id})

    def delete_workspace(self, workspace_id: str):
        try:
            self._client.delete_collection(f"ws_{workspace_id}")
        except Exception:
            pass
