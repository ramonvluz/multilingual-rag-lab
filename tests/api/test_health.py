import asyncio
import tomllib
from importlib.metadata import version
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from multilingual_rag_lab.adapters.inbound.api import app as api_module
from multilingual_rag_lab.bootstrap.settings import Settings
from multilingual_rag_lab.domain import errors
from multilingual_rag_lab.domain.models import Chunk, Document, QueryResult, Source


def test_liveness_is_independent_from_qdrant_and_readiness_is_not(monkeypatch) -> None:
    def unavailable():
        raise RuntimeError("isolated unavailable dependency")

    monkeypatch.setattr(api_module, "build_container", unavailable)
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
        chunk = Chunk.create("fixture", 0, "evidence")
        source = Source("fixture", chunk.chunk_id, "fixture.md", 0.9, "dense")
        return QueryResult(f"evidence [{chunk.chunk_id}]", [source], [chunk.chunk_id], False)


class Container:
    settings = Settings(_env_file=None, upload_max_size=100)
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
        result = client.post("/query", json={"question": "Pergunta"}).json()
        assert result["answer"].startswith("evidence [")
        assert result["abstained"] is False
        assert result["cited_chunk_ids"] == [result["sources"][0]["chunk_id"]]
        assert result["sources"][0]["retrieval_method"] == "dense"
        assert client.delete("/documents/id").status_code == 204


@pytest.mark.parametrize("size,status", [(0, 400), (99, 201), (100, 201), (101, 413)])
def test_upload_limit_and_threadpool(monkeypatch, size, status):
    class ThreadIngest:
        def execute(self, filename, content):
            with pytest.raises(RuntimeError):
                asyncio.get_running_loop()
            return Document.from_content(content, filename, "md"), True

    value = Container()
    value.ingest = ThreadIngest()
    monkeypatch.setattr(api_module, "build_container", lambda: value)
    with TestClient(api_module.create_app()) as client:
        response = client.post("/documents", files={"file": ("notes.md", b"x" * size)})
        assert response.status_code == status
        if status != 201:
            assert set(response.json()) == {"detail"}


def test_query_openapi_and_package_version(monkeypatch):
    monkeypatch.setattr(api_module, "build_container", lambda: Container())
    with TestClient(api_module.create_app()) as client:
        schema = client.get("/openapi.json").json()
    declared = tomllib.loads((Path(__file__).parents[2] / "pyproject.toml").read_text())
    assert schema["info"]["version"] == version("multilingual-rag-lab") == declared["project"]["version"] == "1.0.0"
    response = schema["paths"]["/query"]["post"]["responses"]["200"]
    assert response["content"]["application/json"]["schema"]["$ref"].endswith("/QueryResult")
    models = schema["components"]["schemas"]
    assert set(models["QueryResult"]["properties"]) == {
        "answer", "sources", "cited_chunk_ids", "abstained", "metadata"
    }
    assert models["Source"]["properties"]["retrieval_method"]["enum"] == [
        "dense", "sparse_original", "sparse_normalized"
    ]
    assert "retrieval_method" in models["Source"]["required"]


@pytest.mark.parametrize("question", ["", " ", "\t\r\n"])
def test_blank_question_rejected_before_use_case(monkeypatch, question):
    class NeverQuery:
        def execute(self, value):
            pytest.fail("Blank question reached use case")

    value = Container()
    value.query = NeverQuery()
    monkeypatch.setattr(api_module, "build_container", lambda: value)
    with TestClient(api_module.create_app()) as client:
        response = client.post("/query", json={"question": question})
    assert response.status_code == 422
    assert set(response.json()) == {"detail"}


def test_valid_question_is_not_normalized_and_sparse_provenance_is_serialized(monkeypatch):
    question = "  JÁ entrou?\n"

    class SparseQuery:
        def execute(self, received):
            assert received == question
            chunk = Chunk.create("fixture", 0, "evidence")
            return QueryResult(
                f"answer [{chunk.chunk_id}]",
                [Source("fixture", chunk.chunk_id, "fixture.md", 12.3, "sparse_normalized")],
                [chunk.chunk_id], False,
            )

    value = Container()
    value.query = SparseQuery()
    monkeypatch.setattr(api_module, "build_container", lambda: value)
    with TestClient(api_module.create_app()) as client:
        response = client.post("/query", json={"question": question})
    assert response.status_code == 200
    assert response.json()["sources"][0]["score"] == 12.3
    assert response.json()["sources"][0]["retrieval_method"] == "sparse_normalized"


@pytest.mark.parametrize("operation", ["ingest", "list_documents", "delete", "query"])
@pytest.mark.parametrize(
    "error_type,status",
    [
        (errors.DocumentNotFound, 404), (errors.UnsupportedDocument, 400),
        (errors.MutationBusy, 409), (errors.DependencyUnavailable, 503),
        (errors.IndexNotReady, 503), (errors.IndexIncompatible, 503),
        (errors.LLMProviderError, 502), (errors.DocumentCorrupt, 500),
        (errors.IngestionFailed, 500), (errors.ApplicationError, 500),
    ],
)
def test_application_errors_are_safe_consistent_json(monkeypatch, operation, error_type, status):
    class FailingOperation:
        def execute(self, *args):
            raise error_type("private-internal-diagnostic")

    value = Container()
    setattr(value, operation, FailingOperation())
    monkeypatch.setattr(api_module, "build_container", lambda: value)
    with TestClient(api_module.create_app()) as client:
        if operation == "ingest":
            response = client.post("/documents", files={"file": ("notes.md", b"evidence")})
        elif operation == "list_documents":
            response = client.get("/documents")
        elif operation == "delete":
            response = client.delete("/documents/fixture")
        else:
            response = client.post("/query", json={"question": "question"})
    assert response.status_code == status
    assert response.headers["content-type"] == "application/json"
    assert set(response.json()) == {"detail"}
    assert isinstance(response.json()["detail"], str)
    assert "private-internal-diagnostic" not in response.text
