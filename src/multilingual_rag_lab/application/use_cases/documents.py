from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path

from multilingual_rag_lab.application.ports import (
    Chunker,
    DocumentParser,
    DocumentRepository,
    Embedder,
    KnowledgeStore,
)
from multilingual_rag_lab.domain.errors import (
    DocumentNotFound,
    IngestionFailed,
    UnsupportedDocument,
)
from multilingual_rag_lab.domain.models import Document

SUPPORTED_TYPES = {"pdf", "docx", "html", "md", "csv", "xlsx"}
logger = logging.getLogger(__name__)


@dataclass(slots=True)
class IngestDocument:
    repository: DocumentRepository
    parser: DocumentParser
    chunker: Chunker
    embedder: Embedder
    store: KnowledgeStore
    max_size: int

    def execute(self, filename: str, content: bytes) -> tuple[Document, bool]:
        safe_name = Path(filename).name
        suffix = Path(safe_name).suffix.lower().lstrip(".")
        if not safe_name or "/" in filename or "\\" in filename or suffix not in SUPPORTED_TYPES:
            raise UnsupportedDocument("Unsupported or unsafe filename")
        if not content or len(content) > self.max_size:
            raise IngestionFailed("File is empty or exceeds the configured size limit")
        document = Document.from_content(content, safe_name, suffix)
        try:
            self.repository.get(document.document_id)
            return document, False
        except DocumentNotFound:
            pass
        source = self.repository.save(document, content)
        try:
            chunks = self.chunker.chunk(document.document_id, self.parser.parse(source, suffix))
            if not chunks:
                raise IngestionFailed("No readable content was extracted from the document")
            self.store.upsert(chunks, self.embedder.embed([chunk.text for chunk in chunks]))
        except Exception as error:
            self.repository.delete(document.document_id)
            if isinstance(error, IngestionFailed):
                raise
            logger.exception("ingestion_failed", extra={"document_id": document.document_id})
            raise IngestionFailed("Document ingestion failed") from error
        return document, True


@dataclass(slots=True)
class ListDocuments:
    repository: DocumentRepository

    def execute(self) -> list[Document]:
        return self.repository.list()


@dataclass(slots=True)
class DeleteDocument:
    repository: DocumentRepository
    store: KnowledgeStore

    def execute(self, document_id: str) -> None:
        self.repository.get(document_id)
        self.store.delete_document(document_id)
        self.repository.delete(document_id)
