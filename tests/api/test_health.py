from fastapi.testclient import TestClient

from multilingual_rag_lab.adapters.inbound.api import app as api_module
from multilingual_rag_lab.domain.models import Document, QueryResult


def test_liveness_is_independent_from_qdrant_and_readiness_is_not() -> None:
    with TestClient(api_module.create_app()) as client:
        assert client.get("/health/live").json() == {"status": "live"}
        ready = client.get("/health/ready")
        assert ready.status_code == 503
        assert "dependency" in ready.json()["detail"].lower()


class Store:
    def is_available(self) -> bool:
        return True


class Ingest:
    def execute(self, filename: str, content: bytes) -> tuple[Document, bool]:
        return Document.from_content(content, filename, "md"), True


class Documents:
    def execute(self) -> list[Document]:
        return []


class Delete:
    def execute(self, document_id: str) -> None:
        return None


class Query:
    def execute(self, question: str) -> QueryResult:
        return QueryResult("evidence", [], [], False)


class Container:
    store = Store()
    ingest = Ingest()
    list_documents = Documents()
    delete = Delete()
    query = Query()


def test_public_api_contracts(monkeypatch) -> None:
    monkeypatch.setattr(api_module, "build_container", lambda: Container())
    with TestClient(api_module.create_app()) as client:
        uploaded = client.post(
            "/documents", files={"file": ("notes.md", b"unicode: ol\xc3\xa1", "text/markdown")}
        )
        assert uploaded.status_code == 201 and uploaded.json()["created"] is True
        assert client.get("/documents").json() == []
        assert client.post("/query", json={"question": "Pergunta"}).json()["answer"] == "evidence"
        assert client.delete("/documents/id").status_code == 204
