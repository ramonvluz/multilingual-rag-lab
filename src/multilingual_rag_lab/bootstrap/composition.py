from __future__ import annotations

from dataclasses import dataclass
from functools import partial

from multilingual_rag_lab.adapters.outbound.chunking import HybridChunkerAdapter
from multilingual_rag_lab.adapters.outbound.embeddings import QwenEmbedder
from multilingual_rag_lab.adapters.outbound.llm import GeminiAdapter
from multilingual_rag_lab.adapters.outbound.parsing import DoclingParser
from multilingual_rag_lab.adapters.outbound.storage import FileSystemDocumentRepository
from multilingual_rag_lab.adapters.outbound.storage.locking import mutation_lock
from multilingual_rag_lab.adapters.outbound.vector_store import QdrantKnowledgeStore
from multilingual_rag_lab.application.use_cases import (
    DeleteDocument,
    IngestDocument,
    ListDocuments,
    QueryKnowledge,
    ReindexCorpus,
)
from multilingual_rag_lab.bootstrap.logging import configure_logging
from multilingual_rag_lab.bootstrap.settings import Settings
from multilingual_rag_lab.domain import FileIndexManifest
from multilingual_rag_lab.domain.errors import IndexIncompatible
from multilingual_rag_lab.domain.models import IndexSpec, SparseConfig


@dataclass(slots=True)
class Container:
    settings: Settings
    repository: FileSystemDocumentRepository
    store: QdrantKnowledgeStore
    ingest: IngestDocument
    list_documents: ListDocuments
    delete: DeleteDocument
    query: QueryKnowledge
    index_spec: IndexSpec


def build_container(settings: Settings | None = None) -> Container:
    settings = settings or Settings()
    configure_logging(settings.log_level)
    repository = FileSystemDocumentRepository(settings.runtime_dir / "documents")
    embedder = QwenEmbedder(
        settings.embedding_model,
        settings.embedding_device,
        settings.embedding_dimension,
        settings.embedding_revision,
    )
    store = QdrantKnowledgeStore(settings.qdrant_url)
    chunker = HybridChunkerAdapter(
        settings.embedding_model, settings.chunk_size, settings.embedding_revision
    )
    spec = make_index_spec(settings)
    manifest = FileIndexManifest(settings.runtime_dir / "index" / "manifest.json")
    active = manifest.load()
    if active.spec != spec:
        raise IndexIncompatible(
            "Manifest IndexSpec differs from current configuration; explicit reindex required"
        )
    store.select_active(spec, active.collection_name)
    store.manifest = manifest
    parser = DoclingParser()
    llm = (
        GeminiAdapter(settings.gemini_api_key, settings.llm_model)
        if settings.gemini_api_key
        else None
    )
    lock = partial(mutation_lock, settings.runtime_dir)
    return Container(
        settings,
        repository,
        store,
        IngestDocument(
            repository,
            parser,
            chunker,
            embedder,
            store,
            settings.upload_max_size,
            lock,
            spec.fingerprint,
        ),
        ListDocuments(repository),
        DeleteDocument(repository, store, lock),
        QueryKnowledge(embedder, store, repository, llm, settings.retrieval_top_k),
        spec,
    )


def build_reindex_use_case(settings: Settings | None = None) -> tuple[ReindexCorpus, IndexSpec]:
    """Composition path intentionally independent of an already-active index."""
    settings = settings or Settings()
    configure_logging(settings.log_level)
    repository = FileSystemDocumentRepository(settings.runtime_dir / "documents")
    embedder = QwenEmbedder(
        settings.embedding_model,
        settings.embedding_device,
        settings.embedding_dimension,
        settings.embedding_revision,
    )
    chunker = HybridChunkerAdapter(
        settings.embedding_model, settings.chunk_size, settings.embedding_revision
    )
    spec = make_index_spec(settings)
    store = QdrantKnowledgeStore(settings.qdrant_url)
    manifest = FileIndexManifest(settings.runtime_dir / "index" / "manifest.json")
    return ReindexCorpus(
        repository,
        DoclingParser(),
        chunker,
        embedder,
        store,
        manifest,
        partial(mutation_lock, settings.runtime_dir),
    ), spec


def make_index_spec(settings: Settings) -> IndexSpec:
    return IndexSpec(
        settings.embedding_model,
        settings.embedding_dimension,
        "cosine",
        "docling-hybrid",
        HybridChunkerAdapter.version,
        "qdrant-bm25-idf-v2",
        chunk_size=settings.chunk_size,
        tokenizer=settings.embedding_model,
        embedding_revision=settings.embedding_revision,
        tokenizer_revision=settings.embedding_revision,
        sparse_config=SparseConfig(),
    )
