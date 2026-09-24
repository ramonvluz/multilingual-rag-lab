from __future__ import annotations

import math
from collections.abc import Sequence


def recall_at_k(retrieved: Sequence[str], relevant: set[str], k: int) -> float:
    if not relevant:
        return 0.0
    return len(set(list(dict.fromkeys(retrieved))[:k]) & relevant) / len(relevant)


def reciprocal_rank(retrieved: Sequence[str], relevant: set[str], k: int = 10) -> float:
    for index, item in enumerate(list(dict.fromkeys(retrieved))[:k], start=1):
        if item in relevant:
            return 1 / index
    return 0.0


def ndcg_at_k(retrieved: Sequence[str], relevant: set[str], k: int) -> float:
    actual = sum(
        1 / math.log2(index + 2)
        for index, item in enumerate(list(dict.fromkeys(retrieved))[:k])
        if item in relevant
    )
    ideal = sum(1 / math.log2(index + 2) for index in range(min(k, len(relevant))))
    return actual / ideal if ideal else 0.0
