from multilingual_rag_lab.adapters.outbound.vector_store import QdrantKnowledgeStore
from multilingual_rag_lab.domain.models import Chunk, IndexSpec


def test_qdrant_local_collection_alias_filter_search_and_delete() -> None:
    store = QdrantKnowledgeStore(":memory:")
    spec = IndexSpec("fixture", 2, "cosine", "fixture", "v1")
    candidate = store.create_collection(spec)
    first = Chunk.create("document-a", 0, "olá mundo")
    second = Chunk.create("document-b", 0, "hello world")
    store.upsert_into(candidate, [first, second], [[1.0, 0.0], [0.0, 1.0]])
    assert store.count(candidate) == 2
    store.promote(candidate)
    assert store.search([1.0, 0.0], 1)[0].chunk.document_id == "document-a"
    store.delete_document("document-a")
    assert store.count(candidate) == 1
