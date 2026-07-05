from src.storage import vector_store as vector_store_module
from src.storage.vector_store import VectorStore


def test_vector_store_retries_chroma_client_creation(monkeypatch):
    attempts = {"count": 0}

    class FakeClient:
        pass

    def fake_http_client(host, port):
        attempts["count"] += 1
        if attempts["count"] == 1:
            raise ValueError("not ready")
        return FakeClient()

    monkeypatch.setattr(vector_store_module.chromadb, "HttpClient", fake_http_client)
    monkeypatch.setenv("CHROMA_CONNECT_RETRIES", "2")
    monkeypatch.setenv("CHROMA_CONNECT_RETRY_DELAY", "0")

    store = VectorStore(host="127.0.0.1", port=8001, embedding_fn=object())

    assert isinstance(store._client, FakeClient)
    assert attempts["count"] == 2
