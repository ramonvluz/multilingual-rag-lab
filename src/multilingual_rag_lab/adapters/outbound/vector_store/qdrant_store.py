from __future__ import annotations

import math
from collections.abc import Callable, Sequence
from dataclasses import asdict
from typing import Any
from uuid import NAMESPACE_URL, uuid4, uuid5

from multilingual_rag_lab.domain.errors import (
    DependencyUnavailable,
    IndexIncompatible,
    IndexNotReady,
    IngestionFailed,
)
from multilingual_rag_lab.domain.index_manifest import FileIndexManifest
from multilingual_rag_lab.domain.models import Chunk, IndexSpec, RetrievedChunk, SparseConfig


class QdrantKnowledgeStore:
    """Materialized dense/BM25 index; operational alias or frozen evaluation collection."""

    def __init__(
        self,
        url: str,
        collection_prefix: str = "rag",
        sparse_encoder: Callable[[Sequence[str]], list[Any]] | None = None,
        sparse_config: SparseConfig | None = None,
    ) -> None:
        self.url = url
        self.collection_prefix = collection_prefix
        self.alias_name = f"{collection_prefix}_active"
        self.collection_name: str | None = None
        self._client: Any | None = None
        self._sparse_encoder = sparse_encoder
        self._sparse_model: Any | None = None
        self.sparse_config = sparse_config or SparseConfig()
        self.expected_spec: IndexSpec | None = None
        self.manifest: FileIndexManifest | None = None
        self.materialize_sparse = True

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
        return f"{self.collection_prefix}_{spec.fingerprint}_{uuid4().hex}"

    def create_collection(self, spec: IndexSpec) -> str:
        from qdrant_client.models import (
            Distance,
            Modifier,
            SparseIndexParams,
            SparseVectorParams,
            VectorParams,
        )

        name = self.collection_for(spec)
        if spec.sparse_strategy and (
            spec.sparse_config != self.sparse_config or self.sparse_config.modifier != "idf"
        ):
            raise IndexIncompatible("Materialization configuration differs from IndexSpec")
        self.materialize_sparse = spec.sparse_strategy is not None
        client = self._get_client()
        try:
            client.create_collection(
                name,
                vectors_config={
                    "dense": VectorParams(
                        size=spec.embedding_dimension,
                        distance=Distance(spec.distance_metric.capitalize()),
                    )
                },
                sparse_vectors_config={
                    "bm25": SparseVectorParams(
                        index=SparseIndexParams(on_disk=False), modifier=Modifier.IDF
                    )
                }
                if spec.sparse_strategy
                else None,
            )
        except Exception:
            # A transport error can occur after the server created the collection.
            try:
                if client.collection_exists(name):
                    self.remove_candidate(name)
            except Exception as cleanup_error:
                raise IngestionFailed(
                    f"Candidate creation failed; cleanup uncertain for {name}; reconcile explicitly"
                ) from cleanup_error
            raise
        return name

    def select_active(self, spec: IndexSpec, collection_name: str) -> None:
        if not collection_name.startswith(f"{self.collection_prefix}_{spec.fingerprint}_"):
            raise IndexIncompatible("Manifest collection does not match its IndexSpec")
        self.validate_schema(spec, collection_name)
        if self.active_collection() != collection_name:
            raise IndexIncompatible("Active alias is missing or differs from manifest")
        self.expected_spec = spec
        self.materialize_sparse = spec.sparse_strategy is not None
        self.collection_name = self.alias_name

    def validate_schema(self, spec: IndexSpec, collection_name: str) -> None:
        client = self._get_client()
        if not client.collection_exists(collection_name):
            raise IndexNotReady("Active collection is missing; run `rag-lab reindex`")
        params = client.get_collection(collection_name).config.params
        dense = params.vectors.get("dense") if isinstance(params.vectors, dict) else None
        if (
            dense is None
            or dense.size != spec.embedding_dimension
            or str(dense.distance).lower() != spec.distance_metric.lower()
        ):
            raise IndexIncompatible("Dense vector schema differs from IndexSpec")
        sparse = (params.sparse_vectors or {}).get("bm25")
        if spec.sparse_strategy:
            if (
                spec.sparse_config != self.sparse_config
                or sparse is None
                or str(sparse.modifier).lower() != "idf"
            ):
                raise IndexIncompatible(
                    "BM25 schema/configuration requires the expected IDF strategy"
                )
        elif sparse is not None:
            raise IndexIncompatible("Unexpected sparse vector in dense-only IndexSpec")

    def active_collection(self) -> str | None:
        return next(
            (
                a.collection_name
                for a in self._get_client().get_aliases().aliases
                if a.alias_name == self.alias_name
            ),
            None,
        )

    def promote(self, collection_name: str | None) -> None:
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
        if collection_name is not None:
            actions.append(
                CreateAliasOperation(
                    create_alias=CreateAlias(
                        collection_name=collection_name, alias_name=self.alias_name
                    )
                )
            )
        if actions:
            client.update_collection_aliases(change_aliases_operations=actions)
        self.collection_name = self.alias_name if collection_name is not None else None

    def remove_candidate(self, collection_name: str) -> None:
        if any(
            alias.collection_name == collection_name
            for alias in self._get_client().get_aliases().aliases
        ):
            raise IndexIncompatible("Refusing to delete a collection referenced by an alias")
        self._get_client().delete_collection(collection_name)

    def _collection(self, collection_name: str | None = None) -> str:
        selected = collection_name or self.collection_name
        if selected is None:
            raise IndexNotReady("No active index; run `rag-lab reindex`")
        if (
            selected == self.alias_name
            and self.manifest is not None
            and self.expected_spec is not None
        ):
            manifest = self.manifest.load()
            if manifest.spec != self.expected_spec:
                raise IndexIncompatible(
                    "Runtime configuration is stale; restart against the active manifest"
                )
            self.select_active(self.expected_spec, manifest.collection_name)
        return selected

    def _sparse_vectors(self, texts: Sequence[str], *, query: bool = False) -> list[Any]:
        if self._sparse_encoder is not None:
            return self._sparse_encoder(texts)
        if self._sparse_model is None:
            try:
                from fastembed import SparseTextEmbedding
            except ImportError as error:
                raise DependencyUnavailable("fastembed is unavailable") from error
            config = asdict(self.sparse_config)
            model = config.pop("model")
            config.pop("modifier")
            self._sparse_model = SparseTextEmbedding(model_name=model, **config)
        from qdrant_client.models import SparseVector

        return [
            SparseVector(indices=list(vector.indices), values=list(vector.values))
            for vector in (
                self._sparse_model.query_embed(list(texts))
                if query
                else self._sparse_model.embed(list(texts))
            )
        ]

    def _points(self, chunks: Sequence[Chunk], vectors: Sequence[Sequence[float]]) -> list[Any]:
        from qdrant_client.models import PointStruct

        sparse_vectors = (
            self._sparse_vectors([chunk.text for chunk in chunks])
            if self.materialize_sparse
            else [None] * len(chunks)
        )

        return [
            PointStruct(
                id=str(uuid5(NAMESPACE_URL, chunk.chunk_id)),
                vector={"dense": list(vector), "bm25": sparse_vector}
                if sparse_vector is not None
                else {"dense": list(vector)},
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
            for chunk, vector, sparse_vector in zip(chunks, vectors, sparse_vectors, strict=True)
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
            .query_points(
                self._collection(),
                query=list(vector),
                using="dense",
                limit=limit,
                with_payload=True,
            )
            .points
        )
        return [self._to_retrieved(point) for point in response]

    def sparse_search(self, query: str, limit: int) -> list[RetrievedChunk]:
        sparse_query = self._sparse_vectors([query], query=True)[0]
        response = (
            self._get_client()
            .query_points(
                self._collection(),
                query=sparse_query,
                using="bm25",
                limit=limit,
                with_payload=True,
            )
            .points
        )
        return [self._to_retrieved(point) for point in response]

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

    def document_chunk_ids(self, document_id: str) -> set[str]:
        from qdrant_client.models import FieldCondition, Filter, MatchValue

        records = self.records(
            self._collection(),
            Filter(must=[FieldCondition(key="document_id", match=MatchValue(value=document_id))]),
        )
        return {str(point.payload["chunk_id"]) for point in records}

    def records(
        self, collection: str, query_filter: Any = None, *, vectors: bool = False
    ) -> list[Any]:
        records: list[Any] = []
        offset = None
        while True:
            page, offset = self._get_client().scroll(
                collection,
                scroll_filter=query_filter,
                limit=256,
                offset=offset,
                with_payload=True,
                with_vectors=vectors,
            )
            records.extend(page)
            if offset is None:
                return records

    def validate_contents(
        self,
        spec: IndexSpec,
        collection: str,
        documents: set[str],
        expected_chunks: set[str] | None = None,
    ) -> dict[str, int]:
        self.validate_schema(spec, collection)
        records = self.records(collection, vectors=True)
        observed: dict[str, set[int]] = {}
        chunk_ids: set[str] = set()
        for point in records:
            p, vectors = point.payload or {}, point.vector or {}
            doc = p.get("document_id")
            if doc not in documents:
                raise IndexIncompatible(f"Unknown indexed document: {doc}")
            chunk = Chunk.create(doc, p["chunk_index"], p["text"])
            if (
                p.get("chunk_id") != chunk.chunk_id
                or str(point.id) != str(uuid5(NAMESPACE_URL, chunk.chunk_id))
                or chunk.chunk_id in chunk_ids
            ):
                raise IndexIncompatible("Invalid or duplicate chunk identity")
            dense = vectors.get("dense", [])
            sparse = vectors.get("bm25")
            if (
                len(dense) != spec.embedding_dimension
                or not all(math.isfinite(v) for v in dense)
                or (spec.sparse_strategy and sparse is None)
            ):
                raise IndexIncompatible("Missing/invalid materialized vector")
            chunk_ids.add(chunk.chunk_id)
            indices = observed.setdefault(doc, set())
            if chunk.chunk_index in indices:
                raise IndexIncompatible("Duplicate chunk index")
            indices.add(chunk.chunk_index)
        if set(observed) != documents or any(
            ids != set(range(len(ids))) for ids in observed.values()
        ):
            raise IndexIncompatible("Missing document or incomplete chunk sequence")
        if len(records) != self.count(collection) or (
            expected_chunks is not None and chunk_ids != expected_chunks
        ):
            raise IndexIncompatible("Candidate/index content count or identities differ")
        return {doc: len(ids) for doc, ids in observed.items()}

    def is_available(self) -> bool:
        try:
            if self.expected_spec is None or self.manifest is None:
                return False
            manifest = self.manifest.load()
            if manifest.spec != self.expected_spec:
                return False
            self.select_active(self.expected_spec, manifest.collection_name)
            return True
        except Exception:
            return False
