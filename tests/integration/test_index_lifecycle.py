"""Same contract runs against local Qdrant or an isolated real Server namespace."""

import os
from functools import partial
from uuid import uuid4

import pytest
from qdrant_client.models import Distance, SparseVector, SparseVectorParams, VectorParams

from multilingual_rag_lab.adapters.outbound.storage import FileSystemDocumentRepository
from multilingual_rag_lab.adapters.outbound.storage.locking import mutation_lock
from multilingual_rag_lab.adapters.outbound.vector_store import QdrantKnowledgeStore
from multilingual_rag_lab.application.use_cases.documents import DeleteDocument, IngestDocument
from multilingual_rag_lab.application.use_cases.reindex import ReindexCorpus
from multilingual_rag_lab.domain.errors import IndexIncompatible, IndexNotReady, IngestionFailed
from multilingual_rag_lab.domain.index_manifest import FileIndexManifest, IndexManifest
from multilingual_rag_lab.domain.models import Chunk, Document, IndexSpec, SparseConfig
from multilingual_rag_lab.evaluation.preflight import preflight

SPEC = IndexSpec(
    "fixture",
    2,
    "cosine",
    "docling-hybrid",
    "v1",
    "qdrant-bm25-idf-v2",
    sparse_config=SparseConfig(),
)


@pytest.fixture
def store():
    prefix = "test_remediation_" + uuid4().hex
    value = QdrantKnowledgeStore(
        os.getenv("QDRANT_TEST_URL", ":memory:"),
        prefix,
        sparse_encoder=lambda texts: [SparseVector(indices=[1], values=[1.0]) for _ in texts],
    )
    yield value
    value.promote(None)
    for collection in value._get_client().get_collections().collections:
        if collection.name.startswith(prefix + "_"):
            value.remove_candidate(collection.name)
    value._get_client().close()


class Parser:
    def parse(self, path, file_type):
        return path.read_text()


class Chunker:
    def chunk(self, doc, parsed):
        return [Chunk.create(doc, i, text) for i, text in enumerate(parsed.splitlines())]


class Embedder:
    def embed(self, texts):
        return [[1.0, 0.0] for _ in texts]


def setup_runtime(tmp_path, store):
    repo = FileSystemDocumentRepository(tmp_path / "documents")
    doc = Document.from_content(b"first\nsecond", "source.md", "md")
    repo.save(doc, b"first\nsecond")
    manifest = FileIndexManifest(tmp_path / "index/manifest.json")
    reindex = ReindexCorpus(
        repo, Parser(), Chunker(), Embedder(), store, manifest, partial(mutation_lock, tmp_path)
    )
    return repo, doc, manifest, reindex


def test_unique_candidates_idf_and_rebuild(tmp_path, store):
    repo, doc, manifest, reindex = setup_runtime(tmp_path, store)
    assert reindex.execute(SPEC) == 2
    old = store.active_collection()
    assert reindex.execute(SPEC) == 2
    new = store.active_collection()
    assert old != new and store.count(old) == store.count(new) == 2
    assert manifest.load().collection_name == new
    store.select_active(SPEC, new)
    store.manifest = manifest
    assert store.is_available()
    assert store.sparse_search("synthetic", 2)
    counts = preflight(store, manifest.load(), SPEC, {doc.document_id: "DOC-001"})
    assert counts == {doc.document_id: 2}
    store.promote(old)
    store.collection_name = new
    store._get_client().delete_collection(old)
    assert store.search([1, 0], 2)  # Frozen physical collection remains usable.


@pytest.mark.parametrize("initial", [True, False])
def test_manifest_failure_rolls_back(tmp_path, store, monkeypatch, initial):
    repo, doc, manifest, reindex = setup_runtime(tmp_path, store)
    if not initial:
        reindex.execute(SPEC)
    old = store.active_collection()
    before = manifest.path.read_bytes() if manifest.path.exists() else None
    names = {c.name for c in store._get_client().get_collections().collections}

    def fail(value):
        raise OSError("simulated save failure")

    monkeypatch.setattr(manifest, "save", fail)
    with pytest.raises(OSError):
        reindex.execute(SPEC)
    assert store.active_collection() == old
    assert store.collection_name == (store.alias_name if old else None)
    assert (manifest.path.read_bytes() if manifest.path.exists() else None) == before
    assert {c.name for c in store._get_client().get_collections().collections} == names


def test_failed_build_keeps_active_and_cleans_candidate(tmp_path, store, monkeypatch):
    _, _, manifest, reindex = setup_runtime(tmp_path, store)
    reindex.execute(SPEC)
    old = store.active_collection()

    def fail(texts):
        raise RuntimeError("embedding failed")

    monkeypatch.setattr(reindex.embedder, "embed", fail)
    with pytest.raises(RuntimeError):
        reindex.execute(SPEC)
    assert store.active_collection() == old and store.count(old) == 2
    assert manifest.load().collection_name == old


def test_create_response_failure_cleans_only_new_candidate(tmp_path, store, monkeypatch):
    _, _, manifest, reindex = setup_runtime(tmp_path, store)
    reindex.execute(SPEC)
    old = store.active_collection()
    client = store._get_client()
    names = {c.name for c in client.get_collections().collections}
    create = client.create_collection

    def lost_response(*args, **kwargs):
        create(*args, **kwargs)
        raise RuntimeError("simulated response lost after creation")

    monkeypatch.setattr(client, "create_collection", lost_response)
    with pytest.raises(RuntimeError, match="response lost"):
        reindex.execute(SPEC)
    assert store.active_collection() == old
    assert manifest.load().collection_name == old
    assert {c.name for c in client.get_collections().collections} == names


def test_reindex_lock_and_cleanup_failure_are_explicit(tmp_path, store, monkeypatch):
    _, _, manifest, reindex = setup_runtime(tmp_path, store)
    with mutation_lock(tmp_path), pytest.raises(IngestionFailed, match="Another mutation"):
        reindex.execute(SPEC)
    reindex.execute(SPEC)
    old = store.active_collection()

    def fail(*args):
        raise OSError("simulated unavailable operation")

    monkeypatch.setattr(reindex.embedder, "embed", fail)
    with monkeypatch.context() as patch:
        patch.setattr(store, "remove_candidate", fail)
        with pytest.raises(IngestionFailed, match="candidate test_remediation_"):
            reindex.execute(SPEC)
    assert store.active_collection() == old and manifest.load().collection_name == old


@pytest.mark.parametrize(
    "fault",
    [
        "alias_missing",
        "alias_wrong",
        "collection_missing",
        "dimension",
        "distance",
        "sparse_missing",
        "idf_missing",
    ],
)
def test_select_active_schema_fail_closed(store, fault, tmp_path):
    name = store.create_collection(SPEC)
    store.promote(name)
    if fault == "alias_missing":
        store.promote(None)
    elif fault == "alias_wrong":
        store.promote(store.create_collection(SPEC))
    elif fault == "collection_missing":
        store._get_client().delete_collection(name)
    else:
        store._get_client().delete_collection(name)
        store._get_client().create_collection(
            name,
            vectors_config={
                "dense": VectorParams(
                    size=3 if fault == "dimension" else 2,
                    distance=Distance.DOT if fault == "distance" else Distance.COSINE,
                )
            },
            sparse_vectors_config=None
            if fault == "sparse_missing"
            else {"bm25": SparseVectorParams(modifier=None if fault == "idf_missing" else "idf")},
        )
        store.promote(name)
    with pytest.raises((IndexIncompatible, IndexNotReady)):
        store.select_active(SPEC, name)
    manifest = FileIndexManifest(tmp_path / "manifest.json")
    manifest.save(IndexManifest(SPEC, name))
    store.expected_spec, store.manifest = SPEC, manifest
    assert not store.is_available()


def test_preflight_missing_foreign_document_and_count(tmp_path, store):
    repo, doc, manifest, reindex = setup_runtime(tmp_path, store)
    reindex.execute(SPEC)
    with pytest.raises(IndexIncompatible, match="Missing"):
        preflight(store, manifest.load(), SPEC, {doc.document_id: "DOC-001", "absent": "DOC-002"})
    extra = Chunk.create("foreign", 0, "unregistered")
    store.upsert([extra], [[0, 1]])
    with pytest.raises(IndexIncompatible, match="Unknown"):
        preflight(store, manifest.load(), SPEC, {doc.document_id: "DOC-001"})


def test_ingest_repair_partial_upsert_retry_delete(tmp_path, store, monkeypatch):
    repo, doc, manifest, reindex = setup_runtime(tmp_path, store)
    name = store.create_collection(SPEC)
    store.promote(name)
    use = IngestDocument(
        repo, Parser(), Chunker(), Embedder(), store, 100, index_fingerprint=SPEC.fingerprint
    )
    repaired, created = use.execute("renamed.md", b"first\nsecond")
    assert created and repaired.filename == "source.md" and store.count(name) == 2
    same, created = use.execute("another.md", b"first\nsecond")
    assert not created and same == repaired
    store.delete_document(doc.document_id)
    store.upsert([Chunk.create(doc.document_id, 0, "first")], [[1, 0]])
    assert use.execute("source.md", b"first\nsecond")[1] is True
    assert store.count(name) == 2
    store.delete_document(doc.document_id)
    original = store.upsert

    def fail_after_write(chunks, vectors):
        original(chunks, vectors)
        raise RuntimeError("lost response after successful write")

    monkeypatch.setattr(store, "upsert", fail_after_write)
    with pytest.raises(IngestionFailed, match="retained"):
        use.execute("source.md", b"first\nsecond")
    assert store.count(name) == 0 and repo.get(doc.document_id)
    monkeypatch.setattr(store, "upsert", original)
    use.execute("source.md", b"first\nsecond")
    assert store.count(name) == 2
    original_delete = repo.delete

    def fail_delete(doc_id):
        raise OSError("filesystem temporarily unavailable")

    monkeypatch.setattr(repo, "delete", fail_delete)
    with pytest.raises(OSError):
        DeleteDocument(repo, store).execute(doc.document_id)
    assert store.count(name) == 0
    monkeypatch.setattr(repo, "delete", original_delete)
    DeleteDocument(repo, store).execute(doc.document_id)
    assert repo.list() == []


def test_compensation_failure_retains_source_and_retry_converges(tmp_path, store, monkeypatch):
    repo, doc, _, _ = setup_runtime(tmp_path, store)
    store.promote(store.create_collection(SPEC))
    use = IngestDocument(repo, Parser(), Chunker(), Embedder(), store, 100)
    upsert, delete = store.upsert, store.delete_document

    def uncertain(chunks, vectors):
        upsert(chunks, vectors)
        raise RuntimeError("lost reply")

    calls = 0

    def compensate(doc_id):
        nonlocal calls
        calls += 1
        if calls == 2:
            raise RuntimeError("compensation unavailable")
        delete(doc_id)

    with monkeypatch.context() as patch:
        patch.setattr(store, "upsert", uncertain)
        patch.setattr(store, "delete_document", compensate)
        with pytest.raises(IngestionFailed, match="compensation failed"):
            use.execute("source.md", b"first\nsecond")
    assert repo.get(doc.document_id)
    use.execute("source.md", b"first\nsecond")
    assert len(store.document_chunk_ids(doc.document_id)) == 2


def test_dense_only_spec_materializes_only_dense(store):
    from dataclasses import replace

    spec = replace(SPEC, sparse_strategy=None, sparse_config=None)
    name = store.create_collection(spec)
    store.promote(name)
    chunk = Chunk.create("document", 0, "evidence")
    store.upsert([chunk], [[1, 0]])
    assert store.validate_contents(spec, name, {"document"}) == {"document": 1}


def test_physical_snapshot_does_not_follow_alias(tmp_path, store):
    repo, doc, manifest, reindex = setup_runtime(tmp_path, store)
    reindex.execute(SPEC)
    preflight(store, manifest.load(), SPEC, {doc.document_id: "DOC-001"})
    physical = store.collection_name
    other = store.create_collection(SPEC)
    # Simulate an external process moving the alias, not this backend's promote().
    from qdrant_client.models import (
        CreateAlias,
        CreateAliasOperation,
        DeleteAlias,
        DeleteAliasOperation,
    )

    store._get_client().update_collection_aliases(
        change_aliases_operations=[
            DeleteAliasOperation(delete_alias=DeleteAlias(alias_name=store.alias_name)),
            CreateAliasOperation(
                create_alias=CreateAlias(alias_name=store.alias_name, collection_name=other)
            ),
        ]
    )
    assert store.collection_name == physical
    assert len(store.search([1, 0], 10)) == 2 and len(store.sparse_search("synthetic", 10)) == 2


@pytest.mark.skipif(
    not os.getenv("RUN_BM25_REAL"),
    reason="Explicit real FastEmbed validation (downloads small BM25 resources)",
)
def test_real_fastembed_bm25_server_idf(store):
    store._sparse_encoder = None
    name = store.create_collection(SPEC)
    store.promote(name)
    chunks = [
        Chunk.create("synthetic", i, text)
        for i, text in enumerate(["common rare", "common", "common"])
    ]
    store.upsert(chunks, [[1, 0]] * 3)
    store.validate_schema(SPEC, name)
    assert store.sparse_search("rare", 3)[0].score > store.sparse_search("common", 3)[0].score
    assert store._sparse_vectors(["rare rare"], query=True)[0].values == [1.0]
    assert store._sparse_vectors(["the"], query=True)[0].indices
    assert (
        store._sparse_vectors(["running"], query=True)[0].indices
        != store._sparse_vectors(["run"], query=True)[0].indices
    )
    assert store._sparse_vectors(["permissões"], query=True)[0].indices
