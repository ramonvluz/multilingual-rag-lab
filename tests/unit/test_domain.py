from multilingual_rag_lab.domain.models import Chunk, Document, IndexSpec


def test_content_identity_is_deterministic() -> None:
    first = Document.from_content("Olá mundo".encode(), "one.md", "md")
    second = Document.from_content("Olá mundo".encode(), "two.md", "md")
    assert first.document_id == second.document_id == first.content_hash


def test_chunk_identity_is_deterministic() -> None:
    assert Chunk.create("document", 0, "evidence") == Chunk.create("document", 0, "evidence")


def test_index_spec_fingerprint_changes_for_index_affecting_configuration() -> None:
    baseline = IndexSpec("model", 1024, "cosine", "hybrid", "v1", "bm25")
    changed = IndexSpec("model", 768, "cosine", "hybrid", "v1", "bm25")
    assert baseline.fingerprint != changed.fingerprint
