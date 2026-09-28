from __future__ import annotations

import importlib
from typing import Any

from multilingual_rag_lab.domain.errors import DependencyUnavailable
from multilingual_rag_lab.domain.models import Chunk


class HybridChunkerAdapter:
    """Lazy Docling HybridChunker using the Qwen tokenizer and structural metadata."""

    version = "docling-hybrid-v1"

    def __init__(
        self, tokenizer_name: str, max_tokens: int = 512, revision: str | None = None
    ) -> None:
        self.tokenizer_name = tokenizer_name
        self.max_tokens = max_tokens
        self.revision = revision
        self._chunker: Any | None = None

    def _load(self) -> Any:
        if self._chunker is None:
            try:
                from docling_core.transforms.chunker.tokenizer.huggingface import (
                    HuggingFaceTokenizer,
                )
                from transformers import AutoTokenizer

                hybrid_chunker = importlib.import_module("docling.chunking").HybridChunker
            except ImportError as error:
                raise DependencyUnavailable("Docling HybridChunker is unavailable") from error
            self._chunker = hybrid_chunker(
                tokenizer=HuggingFaceTokenizer(
                    tokenizer=AutoTokenizer.from_pretrained(
                        self.tokenizer_name, revision=self.revision
                    ),
                    max_tokens=self.max_tokens,
                )
            )
        return self._chunker

    def chunk(self, document_id: str, document: object) -> list[Chunk]:
        chunks: list[Chunk] = []
        for native_chunk in self._load().chunk(dl_doc=document):
            headings = getattr(getattr(native_chunk, "meta", None), "headings", None) or []
            section = " > ".join(str(item) for item in headings) or None
            chunks.append(
                Chunk.create(
                    document_id,
                    len(chunks),
                    str(native_chunk.text),
                    section=section,
                    metadata={"chunking": self.version},
                )
            )
        return chunks
