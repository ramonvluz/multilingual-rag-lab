from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from multilingual_rag_lab.domain.errors import DependencyUnavailable
from multilingual_rag_lab.domain.models import RetrievedChunk


class QwenReranker:
    """Explicitly loaded Qwen3 reranker used only by offline evaluation variant C."""

    def __init__(self, model_name: str = "Qwen/Qwen3-Reranker-0.6B", device: str = "cpu") -> None:
        self.model_name, self.device, self._model = model_name, device, None

    def _load(self) -> Any:
        if self._model is None:
            try:
                from sentence_transformers import CrossEncoder
            except ImportError as error:
                raise DependencyUnavailable("sentence-transformers is unavailable") from error
            self._model = CrossEncoder(self.model_name, device=self.device, trust_remote_code=True)
        return self._model

    def rerank(
        self, query: str, chunks: Sequence[RetrievedChunk], limit: int
    ) -> list[RetrievedChunk]:
        if not chunks:
            return []
        scores = self._load().predict([(query, item.chunk.text) for item in chunks])
        ranked = sorted(
            zip(chunks, scores, strict=True), key=lambda pair: float(pair[1]), reverse=True
        )
        return [RetrievedChunk(item.chunk, float(score)) for item, score in ranked[:limit]]
