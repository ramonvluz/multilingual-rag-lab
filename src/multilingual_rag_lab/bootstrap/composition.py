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
)
from multilingual_rag_lab.bootstrap.settings import Settings
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


def build_container(settings: Settings | None = None) -> Container:
    settings = settings or Settings()
    repository = FileSystemDocumentRepository(settings.runtime_dir / "documents")
    embedder = QwenEmbedder(
        settings.embedding_model, settings.embedding_device, settings.embedding_dimension
    )
    store = QdrantKnowledgeStore(settings.qdrant_url)
    spec = IndexSpec(
        settings.embedding_model,
        settings.embedding_dimension,
        "cosine",
        "docling-hybrid",
        HybridChunkerAdapter.version,
        "bm25",
    )
    store.ensure_index(spec)
    parser, chunker = DoclingParser(), HybridChunkerAdapter(settings.chunk_size)
    llm = (
        GeminiAdapter(settings.gemini_api_key, settings.llm_model)
        if settings.gemini_api_key
        else None
    )
    return Container(
        settings,
        repository,
        store,
        IngestDocument(repository, parser, chunker, embedder, store, settings.upload_max_size),
        ListDocuments(repository),
        DeleteDocument(repository, store),
        QueryKnowledge(embedder, store, repository, llm, settings.retrieval_top_k),
    )
