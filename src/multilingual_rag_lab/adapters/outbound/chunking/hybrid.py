from __future__ import annotations

import re

from multilingual_rag_lab.domain.models import Chunk


class HybridChunkerAdapter:
    """Structure-friendly baseline with a token-sized, deterministic text fallback.

    Docling performs parsing; chunk boundaries are kept local and reproducible so the
    application remains testable without loading a tokenizer at import time.
    """

    version = "hybrid-v1"

    def __init__(self, max_tokens: int = 512) -> None:
        self.max_tokens = max_tokens

    def chunk(self, document_id: str, text: str) -> list[Chunk]:
        paragraphs = [part.strip() for part in re.split(r"\n\s*\n", text) if part.strip()]
        chunks: list[Chunk] = []
        buffer: list[str] = []
        section: str | None = None
        for paragraph in paragraphs:
            if paragraph.startswith("#"):
                section = paragraph.lstrip("# ").strip()
            words = paragraph.split()
            while words:
                room = self.max_tokens - len(buffer)
                buffer.extend(words[:room])
                words = words[room:]
                if len(buffer) >= self.max_tokens:
                    chunks.append(
                        Chunk.create(document_id, len(chunks), " ".join(buffer), section=section)
                    )
                    buffer = []
        if buffer:
            chunks.append(Chunk.create(document_id, len(chunks), " ".join(buffer), section=section))
        return chunks
