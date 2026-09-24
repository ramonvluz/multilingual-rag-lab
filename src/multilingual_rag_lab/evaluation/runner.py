from __future__ import annotations

import time
from collections import defaultdict
from dataclasses import asdict
from datetime import UTC, datetime
from typing import Any, Protocol, cast

from multilingual_rag_lab.domain.models import IndexSpec, RetrievedChunk
from multilingual_rag_lab.evaluation.dataset import validate_dataset
from multilingual_rag_lab.evaluation.metrics import ndcg_at_k, recall_at_k, reciprocal_rank
from multilingual_rag_lab.evaluation.reporting import summarize
from multilingual_rag_lab.evaluation.retrieval import reciprocal_rank_fusion


class RetrievalBackend(Protocol):
    def dense(self, query: str, limit: int) -> list[RetrievedChunk]: ...
    def sparse(self, query: str, limit: int) -> list[RetrievedChunk]: ...
    def rerank(
        self, query: str, candidates: list[RetrievedChunk], limit: int
    ) -> list[RetrievedChunk]: ...


class ExperimentalRetriever:
    """Experimental Qdrant dense/sparse retrieval, with optional Qwen reranking."""

    def __init__(self, embedder: Any, store: Any, reranker: Any | None = None) -> None:
        self.embedder, self.store, self.reranker = embedder, store, reranker

    def dense(self, query: str, limit: int) -> list[RetrievedChunk]:
        return cast(list[RetrievedChunk], self.store.search(self.embedder.embed([query])[0], limit))

    def sparse(self, query: str, limit: int) -> list[RetrievedChunk]:
        return cast(list[RetrievedChunk], self.store.sparse_search(query, limit))

    def rerank(
        self, query: str, candidates: list[RetrievedChunk], limit: int
    ) -> list[RetrievedChunk]:
        if self.reranker is None:
            raise RuntimeError("Reranker was not configured for variant C")
        return cast(list[RetrievedChunk], self.reranker.rerank(query, candidates, limit))


WARMUP_QUERY = "OrbeFlow retrieval warm-up"


def retrieve_candidates(
    backend: RetrievalBackend, variant: str, query: str, candidate_pool: int
) -> list[RetrievedChunk]:
    dense = backend.dense(query, candidate_pool)
    if variant == "dense":
        return dense
    sparse = backend.sparse(query, candidate_pool)
    ranks = reciprocal_rank_fusion(
        [[item.chunk.chunk_id for item in dense], [item.chunk.chunk_id for item in sparse]]
    )
    candidates = {item.chunk.chunk_id: item for item in [*dense, *sparse]}
    fused = [candidates[item_id] for item_id in ranks]
    if variant == "hybrid_rerank":
        if not fused:
            raise ValueError("No candidates for reranking; cannot guarantee reranker warm-up")
        return backend.rerank(query, fused, len(fused))
    return fused


def document_ranking(chunks: list[RetrievedChunk], document_ids: dict[str, str]) -> list[str]:
    ranking: dict[str, None] = {}
    for item in chunks:
        operational_id = item.chunk.document_id
        if operational_id not in document_ids:
            raise ValueError(
                f"Retrieved document SHA is not mapped to the corpus: {operational_id}"
            )
        ranking.setdefault(document_ids[operational_id], None)
    return list(ranking)


def run_retrieval_evaluation(
    rows: list[dict[str, Any]],
    backend: RetrievalBackend,
    variant: str,
    document_ids: dict[str, str],
    index_spec: IndexSpec,
    *,
    max_document_k: int = 10,
    candidate_pool: int = 30,
    provenance: dict[str, Any] | None = None,
) -> dict[str, Any]:
    validate_dataset(rows)
    if variant not in {"dense", "hybrid", "hybrid_rerank"}:
        raise ValueError(f"Unknown retrieval variant: {variant}")
    if max_document_k < 10 or candidate_pool < max_document_k:
        raise ValueError("V1 requires max_document_k >= 10 and candidate_pool >= max_document_k")
    if len(set(document_ids.values())) != len(document_ids):
        raise ValueError("Ambiguous document ID mapping")
    for row in rows:
        missing = set(row["relevant_documents"]) - set(document_ids.values())
        if missing:
            raise ValueError(
                f"{row['query_id']}: DOC IDs missing from manifest/runtime mapping: {sorted(missing)}"
            )
    # Execute the entire chosen path before starting any latency timer.
    document_ranking(
        retrieve_candidates(backend, variant, WARMUP_QUERY, candidate_pool), document_ids
    )
    results = []
    for row in rows:
        if row["answerability"] == "unanswerable":
            results.append(
                {
                    **row,
                    "evaluation_group": "unanswerable_abstention",
                    "retrieved_documents": [],
                    "retrieved_chunks": [],
                    "metrics": None,
                    "latency_ms": None,
                    "status": "deferred_to_grounded_generation",
                }
            )
            continue
        started = time.perf_counter()
        retrieved = retrieve_candidates(backend, variant, row["query"], candidate_pool)
        ids = document_ranking(retrieved, document_ids)[:max_document_k]
        latency_ms = (time.perf_counter() - started) * 1000
        relevant = set(row["relevant_documents"])
        results.append(
            {
                **row,
                "evaluation_group": "positive_retrieval",
                "status": "evaluated",
                "retrieved_documents": ids,
                "retrieved_chunks": [
                    {
                        "chunk_id": item.chunk.chunk_id,
                        "document_id": item.chunk.document_id,
                        "corpus_document_id": document_ids[item.chunk.document_id],
                        "score": item.score,
                    }
                    for item in retrieved
                ],
                "document_pool_exhausted": len(ids) < max_document_k,
                "metrics": {
                    **{f"recall_at_{k}": recall_at_k(ids, relevant, k) for k in (1, 3, 5)},
                    "mrr_at_10": reciprocal_rank(ids, relevant, 10),
                    **{f"ndcg_at_{k}": ndcg_at_k(ids, relevant, k) for k in (5, 10)},
                },
                "latency_ms": latency_ms,
            }
        )

    def group(field: str) -> dict[str, Any]:
        grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for item in results:
            grouped[item[field]].append(item)
        return {key: summarize(value) for key, value in grouped.items()}

    return {
        "metadata": {
            **(provenance or {}),
            "timestamp": datetime.now(UTC).isoformat(),
            "report_schema_version": "1.0.0",
            "variant": variant,
            "embedding_model": index_spec.embedding_model,
            "sparse_strategy": index_spec.sparse_strategy if variant != "dense" else None,
            "reranker": "Qwen/Qwen3-Reranker-0.6B" if variant == "hybrid_rerank" else None,
            "index_spec": asdict(index_spec),
            "index_fingerprint": index_spec.fingerprint,
            "document_id_mapping": document_ids,
            "max_document_k": max_document_k,
            "candidate_pool_per_branch": candidate_pool,
            "fusion": "RRF (constant=60), full union" if variant != "dense" else None,
            "rerank_pool": "full fused union, before document deduplication"
            if variant == "hybrid_rerank"
            else None,
            "scoring": "binary document relevance; first occurrence deduplication; macro-average over answerable queries",
            "warmup_policy": {
                "query": WARMUP_QUERY,
                "runs_per_variant": 1,
                "full_retrieval_path": True,
                "model_initialization_excluded": True,
            },
            "latency_policy": "warm-state, answerable only; retrieval through document deduplication; excludes warm-up, mapping setup, metrics and serialization; percentiles linear at (n-1)*p",
            "unanswerable_policy": "preserved, not retrieved/scored; deferred abstention dataset",
        },
        "aggregate": summarize(results),
        "by_primary_type": group("primary_type"),
        "by_query_language": group("query_language"),
        "queries": results,
    }
