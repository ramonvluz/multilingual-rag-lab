from __future__ import annotations

from collections.abc import Sequence
from typing import Any
from uuid import NAMESPACE_URL, uuid5

from multilingual_rag_lab.domain.errors import DependencyUnavailable, IndexIncompatible
from multilingual_rag_lab.domain.models import Chunk, IndexSpec, RetrievedChunk


class QdrantKnowledgeStore:
    def __init__(self, url: str, collection_prefix: str = "rag") -> None:
        self.url = url
        self.collection_prefix = collection_prefix
        self.collection_name: str | None = None
        self._client: Any | None = None

    def _get_client(self) -> Any:
        if self._client is None:
            try:
                from qdrant_client import QdrantClient
            except ImportError as error:
                raise DependencyUnavailable("qdrant-client is unavailable") from error
            self._client = QdrantClient(url=self.url, timeout=5)
        return self._client

    def ensure_index(self, spec: IndexSpec) -> None:
        from qdrant_client.models import Distance, VectorParams

        client: Any = self._get_client()
        name = f"{self.collection_prefix}_{spec.fingerprint}"
        if client.collection_exists(name):
            info = client.get_collection(name)
            if info.config.params.vectors.size != spec.embedding_dimension:
                raise IndexIncompatible("Existing collection does not match IndexSpec")
        else:
            client.create_collection(
                name,
                vectors_config=VectorParams(
                    size=spec.embedding_dimension, distance=Distance.COSINE
                ),
            )
        self.collection_name = name

    def _collection(self) -> str:
        if self.collection_name is None:
            raise IndexIncompatible("Index has not been initialized")
        return self.collection_name

    def upsert(self, chunks: Sequence[Chunk], vectors: Sequence[Sequence[float]]) -> None:
        from qdrant_client.models import PointStruct

        points = [
            PointStruct(
                id=str(uuid5(NAMESPACE_URL, chunk.chunk_id)),
                vector=list(vector),
                payload={
                    "chunk_id": chunk.chunk_id,
                    "document_id": chunk.document_id,
                    "chunk_index": chunk.chunk_index,
                    "text": chunk.text,
                    "page": chunk.page,
                    "section": chunk.section,
                    "metadata": chunk.metadata,
                },
            )
            for chunk, vector in zip(chunks, vectors, strict=True)
        ]
        self._get_client().upsert(self._collection(), points=points, wait=True)

    def search(self, vector: Sequence[float], limit: int) -> list[RetrievedChunk]:
        response = (
            self._get_client()
            .query_points(self._collection(), query=list(vector), limit=limit, with_payload=True)
            .points
        )
        return [
            RetrievedChunk(
                Chunk(
                    str(point.payload["chunk_id"]),
                    str(point.payload["document_id"]),
                    int(point.payload["chunk_index"]),
                    str(point.payload["text"]),
                    point.payload.get("page"),
                    point.payload.get("section"),
                    dict(point.payload.get("metadata", {})),
                ),
                float(point.score),
            )
            for point in response
        ]

    def delete_document(self, document_id: str) -> None:
        from qdrant_client.models import FieldCondition, Filter, FilterSelector, MatchValue

        selector = FilterSelector(
            filter=Filter(
                must=[FieldCondition(key="document_id", match=MatchValue(value=document_id))]
            )
        )
        self._get_client().delete(self._collection(), points_selector=selector, wait=True)

    def is_available(self) -> bool:
        try:
            self._get_client().get_collections()
            return True
        except Exception:
            return False
