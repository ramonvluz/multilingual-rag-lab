from qdrant_client.models import SparseVector

from multilingual_rag_lab.adapters.outbound.vector_store import QdrantKnowledgeStore
from multilingual_rag_lab.domain.models import Chunk, IndexSpec
from multilingual_rag_lab.evaluation.retrieval import reciprocal_rank_fusion


def sparse_encoder(texts: list[str]) -> list[SparseVector]:
    vectors = []
    for text in texts:
        if "olá" in text:
            vectors.append(SparseVector(indices=[0], values=[1.0]))
        else:
            vectors.append(SparseVector(indices=[1], values=[1.0]))
    return vectors


def test_qdrant_local_collection_alias_filter_search_and_delete() -> None:
    store = QdrantKnowledgeStore(":memory:", sparse_encoder=sparse_encoder)
    spec = IndexSpec("fixture", 2, "cosine", "fixture", "v1", "qdrant-bm25-v1")
    candidate = store.create_collection(spec)
    first = Chunk.create("document-a", 0, "olá mundo")
    second = Chunk.create("document-b", 0, "hello world")
    store.upsert_into(candidate, [first, second], [[1.0, 0.0], [0.0, 1.0]])
    assert store.count(candidate) == 2
    store.promote(candidate)
    assert store.search([1.0, 0.0], 1)[0].chunk.document_id == "document-a"
    assert store.sparse_search("olá", 1)[0].chunk.document_id == "document-a"
    ranks = reciprocal_rank_fusion(
        [
            [item.chunk.chunk_id for item in store.search([1.0, 0.0], 2)],
            [item.chunk.chunk_id for item in store.sparse_search("olá", 2)],
        ]
    )
    assert ranks[0] == first.chunk_id
    store.delete_document("document-a")
    assert store.count(candidate) == 1
