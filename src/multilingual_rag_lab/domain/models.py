from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from typing import Any


def _stable_hash(value: str | bytes) -> str:
    raw = value.encode("utf-8") if isinstance(value, str) else value
    return hashlib.sha256(raw).hexdigest()


@dataclass(frozen=True, slots=True)
class Document:
    document_id: str
    content_hash: str
    filename: str
    file_type: str
    metadata: dict[str, Any] = field(default_factory=dict)
    ingested_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    @classmethod
    def from_content(cls, content: bytes, filename: str, file_type: str) -> Document:
        digest = _stable_hash(content)
        return cls(document_id=digest, content_hash=digest, filename=filename, file_type=file_type)


@dataclass(frozen=True, slots=True)
class Chunk:
    chunk_id: str
    document_id: str
    chunk_index: int
    text: str
    page: int | None = None
    section: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def create(cls, document_id: str, chunk_index: int, text: str, **kwargs: Any) -> Chunk:
        return cls(
            _stable_hash(f"{document_id}:{chunk_index}:{text}"),
            document_id,
            chunk_index,
            text,
            **kwargs,
        )


@dataclass(frozen=True, slots=True)
class RetrievedChunk:
    chunk: Chunk
    score: float


@dataclass(frozen=True, slots=True)
class Source:
    document_id: str
    chunk_id: str
    filename: str
    score: float


@dataclass(frozen=True, slots=True)
class QueryResult:
    answer: str
    sources: list[Source]
    cited_chunk_ids: list[str]
    abstained: bool
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class IndexSpec:
    embedding_model: str
    embedding_dimension: int
    distance_metric: str
    chunking_strategy: str
    chunking_version: str
    sparse_strategy: str | None = None

    @property
    def fingerprint(self) -> str:
        canonical = json.dumps(asdict(self), sort_keys=True, separators=(",", ":"))
        return _stable_hash(canonical)[:16]
