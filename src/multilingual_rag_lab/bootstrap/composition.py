from __future__ import annotations

from dataclasses import dataclass

from multilingual_rag_lab.adapters.outbound.chunking import HybridChunkerAdapter
from multilingual_rag_lab.adapters.outbound.embeddings import QwenEmbedder
from multilingual_rag_lab.adapters.outbound.llm import GeminiAdapter
from multilingual_rag_lab.adapters.outbound.parsing import DoclingParser
from multilingual_rag_lab.adapters.outbound.storage import FileSystemDocumentRepository
from multilingual_rag_lab.adapters.outbound.vector_store import QdrantKnowledgeStore
from multilingual_rag_lab.application.use_cases import (
    DeleteDocument,
    IngestDocument,
    ListDocuments,
    QueryKnowledge,
    ReindexCorpus,
)
from multilingual_rag_lab.bootstrap.settings import Settings
from multilingual_rag_lab.domain import FileIndexManifest
from multilingual_rag_lab.domain.models import IndexSpec


@dataclass(slots=True)
class Container:
    settings: Settings
    repository: FileSystemDocumentRepository
    store: QdrantKnowledgeStore
    ingest: IngestDocument
    list_documents: ListDocuments
    delete: DeleteDocument
    query: QueryKnowledge
    reindex: ReindexCorpus
    index_spec: IndexSpec


def build_container(settings: Settings | None = None) -> Container:
    settings = settings or Settings()
    repository = FileSystemDocumentRepository(settings.runtime_dir / "documents")
    embedder = QwenEmbedder(
        settings.embedding_model, settings.embedding_device, settings.embedding_dimension
    )
    store = QdrantKnowledgeStore(settings.qdrant_url)
    chunker = HybridChunkerAdapter(settings.embedding_model, settings.chunk_size)
    spec = IndexSpec(
        settings.embedding_model,
        settings.embedding_dimension,
        "cosine",
        "docling-hybrid",
        HybridChunkerAdapter.version,
        None,
    )
    manifest = FileIndexManifest(settings.runtime_dir / "index" / "manifest.json")
    store.select_active(spec, manifest.load().collection_name)
    parser = DoclingParser()
    llm = (
        GeminiAdapter(settings.gemini_api_key, settings.llm_model)
        if settings.gemini_api_key
        else None
    )
    reindex = ReindexCorpus(repository, parser, chunker, embedder, store, manifest)
    return Container(
        settings,
        repository,
        store,
        IngestDocument(repository, parser, chunker, embedder, store, settings.upload_max_size),
        ListDocuments(repository),
        DeleteDocument(repository, store),
        QueryKnowledge(embedder, store, repository, llm, settings.retrieval_top_k),
        reindex,
        spec,
    )


def build_reindex_use_case(settings: Settings | None = None) -> tuple[ReindexCorpus, IndexSpec]:
    """Composition path intentionally independent of an already-active index."""
    settings = settings or Settings()
    repository = FileSystemDocumentRepository(settings.runtime_dir / "documents")
    embedder = QwenEmbedder(
        settings.embedding_model, settings.embedding_device, settings.embedding_dimension
    )
    chunker = HybridChunkerAdapter(settings.embedding_model, settings.chunk_size)
    spec = IndexSpec(
        settings.embedding_model,
        settings.embedding_dimension,
        "cosine",
        "docling-hybrid",
        HybridChunkerAdapter.version,
        None,
    )
    store = QdrantKnowledgeStore(settings.qdrant_url)
    manifest = FileIndexManifest(settings.runtime_dir / "index" / "manifest.json")
    return ReindexCorpus(repository, DoclingParser(), chunker, embedder, store, manifest), spec
