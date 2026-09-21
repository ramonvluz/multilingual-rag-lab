from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class RetrievalReport:
    variant: str
    query_count: int
    recall_at_k: float
    mrr: float
    ndcg_at_k: float
    latency_ms: float
