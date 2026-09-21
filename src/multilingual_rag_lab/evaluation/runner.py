from __future__ import annotations

import json
import time
from collections import defaultdict
from dataclasses import asdict
from pathlib import Path
from typing import Any, Protocol, cast

from multilingual_rag_lab.domain.models import RetrievedChunk
from multilingual_rag_lab.evaluation.metrics import ndcg_at_k, recall_at_k, reciprocal_rank
from multilingual_rag_lab.evaluation.reporting import RetrievalReport
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


def load_dataset(path: Path) -> list[dict[str, Any]]:
    rows = []
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if line.strip():
            row = json.loads(line)
            required = {"query_id", "query", "query_type", "relevant_documents"}
            if not required <= row.keys():
                raise ValueError(f"Dataset row {line_number} misses required fields")
            rows.append(row)
    return rows


def run_retrieval_evaluation(
    rows: list[dict[str, Any]], backend: RetrievalBackend, variant: str, top_k: int
) -> dict[str, Any]:
    results = []
    for row in rows:
        started = time.perf_counter()
        dense = backend.dense(row["query"], top_k * 3)
        if variant == "dense":
            retrieved = dense[:top_k]
        else:
            sparse = backend.sparse(row["query"], top_k * 3)
            ranks = reciprocal_rank_fusion(
                [[item.chunk.chunk_id for item in dense], [item.chunk.chunk_id for item in sparse]]
            )
            candidates = {item.chunk.chunk_id: item for item in [*dense, *sparse]}
            fused = [candidates[item_id] for item_id in ranks]
            retrieved = (
                backend.rerank(row["query"], fused, top_k)
                if variant == "hybrid_rerank"
                else fused[:top_k]
            )
        ids = [item.chunk.document_id for item in retrieved]
        relevant = set(row["relevant_documents"])
        results.append(
            {
                "query_id": row["query_id"],
                "query_type": row["query_type"],
                "recall_at_k": recall_at_k(ids, relevant, top_k),
                "mrr": reciprocal_rank(ids, relevant),
                "ndcg_at_k": ndcg_at_k(ids, relevant, top_k),
                "latency_ms": (time.perf_counter() - started) * 1000,
            }
        )

    def report(items: list[dict[str, Any]], label: str) -> dict[str, Any]:
        report = RetrievalReport(
            variant=label,
            query_count=len(items),
            recall_at_k=sum(item["recall_at_k"] for item in items) / len(items) if items else 0.0,
            mrr=sum(item["mrr"] for item in items) / len(items) if items else 0.0,
            ndcg_at_k=sum(item["ndcg_at_k"] for item in items) / len(items) if items else 0.0,
            latency_ms=sum(item["latency_ms"] for item in items) / len(items) if items else 0.0,
        )
        return asdict(report)

    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for item in results:
        grouped[item["query_type"]].append(item)
    return {
        "aggregate": report(results, variant),
        "by_query_type": {key: report(value, variant) for key, value in grouped.items()},
        "queries": results,
    }
