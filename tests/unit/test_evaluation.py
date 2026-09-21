from multilingual_rag_lab.domain.models import Chunk, RetrievedChunk
from multilingual_rag_lab.evaluation.metrics import ndcg_at_k, recall_at_k, reciprocal_rank
from multilingual_rag_lab.evaluation.retrieval import reciprocal_rank_fusion
from multilingual_rag_lab.evaluation.runner import run_retrieval_evaluation


def test_rrf_fuses_rankings_deterministically() -> None:
    assert reciprocal_rank_fusion([["a", "b"], ["b", "a"]]) == ["a", "b"]


def test_retrieval_metrics() -> None:
    retrieved, relevant = ["a", "b", "c"], {"b", "z"}
    assert recall_at_k(retrieved, relevant, 2) == 0.5
    assert reciprocal_rank(retrieved, relevant) == 0.5
    assert 0 < ndcg_at_k(retrieved, relevant, 3) < 1


class Backend:
    def dense(self, query: str, limit: int) -> list[RetrievedChunk]:
        return [RetrievedChunk(Chunk.create("doc-1", 0, "answer"), 1.0)]

    def sparse(self, query: str, limit: int) -> list[RetrievedChunk]:
        return self.dense(query, limit)

    def rerank(
        self, query: str, candidates: list[RetrievedChunk], limit: int
    ) -> list[RetrievedChunk]:
        return candidates[:limit]


def test_runner_reports_aggregate_and_query_type() -> None:
    report = run_retrieval_evaluation(
        [
            {
                "query_id": "q1",
                "query": "answer",
                "query_type": "semantic",
                "relevant_documents": ["doc-1"],
            }
        ],
        Backend(),
        "hybrid_rerank",
        1,
    )
    assert report["aggregate"]["recall_at_k"] == 1.0
    assert report["by_query_type"]["semantic"]["mrr"] == 1.0
