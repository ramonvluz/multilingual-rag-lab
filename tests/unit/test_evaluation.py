from multilingual_rag_lab.evaluation.metrics import ndcg_at_k, recall_at_k, reciprocal_rank
from multilingual_rag_lab.evaluation.retrieval import reciprocal_rank_fusion


def test_rrf_fuses_rankings_deterministically() -> None:
    assert reciprocal_rank_fusion([["a", "b"], ["b", "a"]]) == ["a", "b"]


def test_retrieval_metrics() -> None:
    retrieved, relevant = ["a", "b", "c"], {"b", "z"}
    assert recall_at_k(retrieved, relevant, 2) == 0.5
    assert reciprocal_rank(retrieved, relevant) == 0.5
    assert 0 < ndcg_at_k(retrieved, relevant, 3) < 1
