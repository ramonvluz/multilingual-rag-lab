from __future__ import annotations

from collections.abc import Sequence
from typing import cast

from multilingual_rag_lab.domain.errors import DependencyUnavailable


class QwenEmbedder:
    def __init__(self, model_name: str, device: str, expected_dimension: int) -> None:
        self.model_name, self.device, self._dimension = model_name, device, expected_dimension
        self._model: object | None = None

    @property
    def dimension(self) -> int:
        return self._dimension

    def _load(self) -> object:
        if self._model is None:
            try:
                from sentence_transformers import SentenceTransformer
            except ImportError as error:
                raise DependencyUnavailable("sentence-transformers is unavailable") from error
            self._model = SentenceTransformer(
                self.model_name, device=self.device, trust_remote_code=True
            )
        return self._model

    def embed(self, texts: Sequence[str]) -> list[list[float]]:
        model = self._load()
        vectors = model.encode(list(texts), normalize_embeddings=True, show_progress_bar=False)  # type: ignore[attr-defined]
        result = cast(list[list[float]], vectors.tolist())
        if result and len(result[0]) != self._dimension:
            raise ValueError(f"Embedding dimension differs from configured {self._dimension}")
        return result
