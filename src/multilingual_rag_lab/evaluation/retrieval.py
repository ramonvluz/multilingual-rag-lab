from __future__ import annotations

from collections import defaultdict
from collections.abc import Sequence


def reciprocal_rank_fusion(rankings: Sequence[Sequence[str]], constant: int = 60) -> list[str]:
    """Fuse ranked candidate IDs without assuming a specific retrieval backend."""
    scores: dict[str, float] = defaultdict(float)
    for ranking in rankings:
        for rank, item_id in enumerate(ranking, start=1):
            scores[item_id] += 1 / (constant + rank)
    return [item_id for item_id, _ in sorted(scores.items(), key=lambda pair: (-pair[1], pair[0]))]
