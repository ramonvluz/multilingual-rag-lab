from pathlib import Path

import pytest

from multilingual_rag_lab.application.use_cases.documents import IngestDocument
from multilingual_rag_lab.domain.errors import DocumentNotFound, UnsupportedDocument
from multilingual_rag_lab.domain.models import Chunk, Document


class Repository:
    def __init__(self, root: Path) -> None:
        self.root, self.docs = root, {}

    def get(self, document_id: str) -> Document:
        if document_id not in self.docs:
            raise DocumentNotFound(document_id)
        return self.docs[document_id]

    def save(self, document: Document, content: bytes) -> Path:
        self.docs[document.document_id] = document
        path = self.root / document.document_id
        path.write_bytes(content)
        return path

    def delete(self, document_id: str) -> None:
        self.docs.pop(document_id, None)


class Parser:
    def parse(self, source: Path, file_type: str) -> str:
        return source.read_text()


class Chunker:
    def chunk(self, document_id: str, text: str) -> list[Chunk]:
        return [Chunk.create(document_id, 0, text)]


class Embedder:
    def embed(self, texts: list[str]) -> list[list[float]]:
        return [[1.0] for _ in texts]


class Store:
    def __init__(self) -> None:
        self.calls = 0

    def upsert(self, chunks: list[Chunk], vectors: list[list[float]]) -> None:
        self.calls += 1


def test_reingestion_is_idempotent(tmp_path: Path) -> None:
    store = Store()
    use_case = IngestDocument(Repository(tmp_path), Parser(), Chunker(), Embedder(), store, 100)
    _, created = use_case.execute("evidence.md", b"unicode: espanhol")
    _, duplicated = use_case.execute("evidence.md", b"unicode: espanhol")
    assert created and not duplicated and store.calls == 1


def test_path_traversal_is_rejected(tmp_path: Path) -> None:
    use_case = IngestDocument(Repository(tmp_path), Parser(), Chunker(), Embedder(), Store(), 100)
    with pytest.raises(UnsupportedDocument):
        use_case.execute("../secret.md", b"no")
