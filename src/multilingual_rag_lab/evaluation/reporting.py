from __future__ import annotations

import math
from statistics import mean
from typing import Any

METRIC_NAMES = ("recall_at_1", "recall_at_3", "recall_at_5", "mrr_at_10", "ndcg_at_5", "ndcg_at_10")


def latency_summary(values: list[float]) -> dict[str, float | None]:
    """Percentiles use linear interpolation at (n - 1) * p."""
    ordered = sorted(values)
    if not ordered:
        return {"mean": None, "p50": None, "p95": None}

    def percentile(p: float) -> float:
        position = (len(ordered) - 1) * p
        lower, upper = math.floor(position), math.ceil(position)
        return ordered[lower] + (ordered[upper] - ordered[lower]) * (position - lower)

    return {"mean": mean(ordered), "p50": percentile(0.50), "p95": percentile(0.95)}


def summarize(items: list[dict[str, Any]]) -> dict[str, Any]:
    positives = [item for item in items if item["answerability"] == "answerable"]
    return {
        "query_count": len(items),
        "positive_query_count": len(positives),
        "unanswerable_count": len(items) - len(positives),
        "metrics": {
            name: mean(item["metrics"][name] for item in positives) if positives else None
            for name in METRIC_NAMES
        },
        "latency_ms": latency_summary([item["latency_ms"] for item in positives]),
    }
