from __future__ import annotations

from collections.abc import Sequence
from typing import Any
from uuid import NAMESPACE_URL, uuid5

from multilingual_rag_lab.domain.errors import (
    DependencyUnavailable,
    IndexIncompatible,
    IndexNotReady,
)
from multilingual_rag_lab.domain.models import Chunk, IndexSpec, RetrievedChunk


class QdrantKnowledgeStore:
    """Dense Qdrant index addressed through a stable alias, never auto-created."""

    def __init__(self, url: str, collection_prefix: str = "rag") -> None:
        self.url = url
        self.collection_prefix = collection_prefix
        self.alias_name = f"{collection_prefix}_active"
        self.collection_name: str | None = None
        self._client: Any | None = None

    def _get_client(self) -> Any:
        if self._client is None:
            try:
                from qdrant_client import QdrantClient
            except ImportError as error:
                raise DependencyUnavailable("qdrant-client is unavailable") from error
            self._client = (
                QdrantClient(location=":memory:")
                if self.url == ":memory:"
                else QdrantClient(url=self.url, timeout=5)
            )
        return self._client

    def collection_for(self, spec: IndexSpec) -> str:
        return f"{self.collection_prefix}_{spec.fingerprint}"

    def create_collection(self, spec: IndexSpec) -> str:
        from qdrant_client.models import Distance, VectorParams

        name = self.collection_for(spec)
        client = self._get_client()
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
        return name

    def select_active(self, spec: IndexSpec, collection_name: str) -> None:
        if collection_name != self.collection_for(spec):
            raise IndexIncompatible("Manifest collection does not match its IndexSpec")
        if not self._get_client().collection_exists(collection_name):
            raise IndexNotReady("Active collection is missing; run `rag-lab reindex`")
        self.collection_name = self.alias_name

    def promote(self, collection_name: str) -> None:
        from qdrant_client.models import (
            CreateAlias,
            CreateAliasOperation,
            DeleteAlias,
            DeleteAliasOperation,
        )

        client = self._get_client()
        aliases = {alias.alias_name for alias in client.get_aliases().aliases}
        actions: list[Any] = []
        if self.alias_name in aliases:
            actions.append(
                DeleteAliasOperation(delete_alias=DeleteAlias(alias_name=self.alias_name))
            )
        actions.append(
            CreateAliasOperation(
                create_alias=CreateAlias(
                    collection_name=collection_name, alias_name=self.alias_name
                )
            )
        )
        client.update_collection_aliases(change_aliases_operations=actions)
        self.collection_name = self.alias_name

    def _collection(self, collection_name: str | None = None) -> str:
        selected = collection_name or self.collection_name
        if selected is None:
            raise IndexNotReady("No active index; run `rag-lab reindex`")
        return selected

    def _points(self, chunks: Sequence[Chunk], vectors: Sequence[Sequence[float]]) -> list[Any]:
        from qdrant_client.models import PointStruct

        return [
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

    def upsert(self, chunks: Sequence[Chunk], vectors: Sequence[Sequence[float]]) -> None:
        self._get_client().upsert(
            self._collection(), points=self._points(chunks, vectors), wait=True
        )

    def upsert_into(
        self, collection_name: str, chunks: Sequence[Chunk], vectors: Sequence[Sequence[float]]
    ) -> None:
        self._get_client().upsert(collection_name, points=self._points(chunks, vectors), wait=True)

    def count(self, collection_name: str) -> int:
        return int(self._get_client().count(collection_name, exact=True).count)

    def search(self, vector: Sequence[float], limit: int) -> list[RetrievedChunk]:
        response = (
            self._get_client()
            .query_points(self._collection(), query=list(vector), limit=limit, with_payload=True)
            .points
        )
        return [self._to_retrieved(point) for point in response]

    def all_chunks(self) -> list[Chunk]:
        points, offset = [], None
        while True:
            batch, offset = self._get_client().scroll(
                self._collection(), offset=offset, limit=256, with_payload=True, with_vectors=False
            )
            points.extend(batch)
            if offset is None:
                break
        return [self._to_retrieved(point).chunk for point in points]

    @staticmethod
    def _to_retrieved(point: Any) -> RetrievedChunk:
        payload = point.payload
        return RetrievedChunk(
            Chunk(
                str(payload["chunk_id"]),
                str(payload["document_id"]),
                int(payload["chunk_index"]),
                str(payload["text"]),
                payload.get("page"),
                payload.get("section"),
                dict(payload.get("metadata", {})),
            ),
            float(point.score),
        )

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
