from pathlib import Path

import pytest

from multilingual_rag_lab.application.use_cases.reindex import ReindexCorpus
from multilingual_rag_lab.domain import FileIndexManifest, IndexManifest
from multilingual_rag_lab.domain.models import Chunk, Document, IndexSpec


class Repository:
    def __init__(self, root: Path) -> None:
        self.document = Document.from_content(b"evidence", "fixture.md", "md")
        self.root = root
        self.root.joinpath("source.md").write_text("evidence")
    def list(self) -> list[Document]: return [self.document]
    def source_path(self, document: Document) -> Path: return self.root / "source.md"


class Parser:
    def parse(self, source: Path, file_type: str) -> object: return source.read_text()


class Chunker:
    def chunk(self, document_id: str, document: object) -> list[Chunk]:
        return [Chunk.create(document_id, 0, str(document))]


class Embedder:
    def embed(self, texts: list[str]) -> list[list[float]]: return [[1.0] for _ in texts]


class Store:
    def __init__(self, fail: bool = False) -> None:
        self.active, self.fail, self.chunks = "old", fail, 0
    def create_collection(self, spec: IndexSpec) -> str: return "candidate"
    def upsert_into(self, collection: str, chunks: list[Chunk], vectors: list[list[float]]) -> None:
        if self.fail:
            raise RuntimeError("simulated indexing failure")
        self.chunks += len(chunks)
    def count(self, collection: str) -> int: return self.chunks
    def promote(self, collection: str) -> None: self.active = collection


def _spec() -> IndexSpec:
    return IndexSpec("model", 1, "cosine", "docling-hybrid", "v1")


def test_reindex_promotes_only_after_validation(tmp_path: Path) -> None:
    store = Store()
    manifest = FileIndexManifest(tmp_path / "manifest.json")
    indexed = ReindexCorpus(Repository(tmp_path), Parser(), Chunker(), Embedder(), store, manifest).execute(_spec())
    assert indexed == 1 and store.active == "candidate"
    assert manifest.load().collection_name == "candidate"


def test_reindex_failure_keeps_active_index_and_manifest(tmp_path: Path) -> None:
    manifest = FileIndexManifest(tmp_path / "manifest.json")
    manifest.save(IndexManifest(_spec(), "old"))
    store = Store(fail=True)
    with pytest.raises(RuntimeError):
        ReindexCorpus(Repository(tmp_path), Parser(), Chunker(), Embedder(), store, manifest).execute(_spec())
    assert store.active == "old" and manifest.load().collection_name == "old"
