from __future__ import annotations

import logging
from collections.abc import Callable
from contextlib import AbstractContextManager, nullcontext
from dataclasses import dataclass, replace
from pathlib import Path

from multilingual_rag_lab.application.ports import (
    Chunker,
    DocumentParser,
    DocumentRepository,
    Embedder,
    KnowledgeStore,
)
from multilingual_rag_lab.domain.errors import (
    DocumentCorrupt,
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
    lock: Callable[[], AbstractContextManager[None]] = nullcontext
    index_fingerprint: str = ""

    def execute(self, filename: str, content: bytes) -> tuple[Document, bool]:
        with self.lock():
            return self._execute(filename, content)

    def _execute(self, filename: str, content: bytes) -> tuple[Document, bool]:
        safe_name = Path(filename).name
        suffix = Path(safe_name).suffix.lower().lstrip(".")
        if not safe_name or "/" in filename or "\\" in filename or suffix not in SUPPORTED_TYPES:
            raise UnsupportedDocument("Unsupported or unsafe filename")
        if not content or len(content) > self.max_size:
            raise IngestionFailed("File is empty or exceeds the configured size limit")
        document = Document.from_content(content, safe_name, suffix)
        existing = False
        try:
            document = self.repository.get(document.document_id)
            existing = True
            receipt = document.metadata.get("index_receipt", {})
            if (
                receipt.get("fingerprint") == self.index_fingerprint
                and receipt.get("chunk_ids")
                and self.store.document_chunk_ids(document.document_id) == set(receipt["chunk_ids"])
            ):
                return document, False
        except (DocumentNotFound, DocumentCorrupt):
            pass
        source = (
            self.repository.source_path(document)
            if existing
            else self.repository.save(document, content)
        )
        attempted = False
        try:
            chunks = self.chunker.chunk(
                document.document_id, self.parser.parse(source, document.file_type)
            )
            if not chunks:
                raise IngestionFailed("No readable content was extracted from the document")
            expected = {chunk.chunk_id for chunk in chunks}
            present = self.store.document_chunk_ids(document.document_id)
            if present != expected:
                vectors = self.embedder.embed([chunk.text for chunk in chunks])
                attempted = True
                self.store.delete_document(document.document_id)
                self.store.upsert(chunks, vectors)
                if self.store.document_chunk_ids(document.document_id) != expected:
                    raise IngestionFailed("Index write is incomplete; retry ingestion")
            document = replace(
                document,
                metadata={
                    **document.metadata,
                    "index_receipt": {
                        "fingerprint": self.index_fingerprint,
                        "chunk_ids": sorted(expected),
                    },
                },
            )
            self.repository.save_metadata(document)
        except Exception as error:
            if attempted:
                try:
                    self.store.delete_document(document.document_id)
                except Exception as compensation_error:
                    logger.error(
                        "ingestion_compensation_failed", extra={"document_id": document.document_id}
                    )
                    raise IngestionFailed(
                        f"Index compensation failed for {document.document_id}; source retained; retry/reconcile required"
                    ) from compensation_error
            logger.error("ingestion_failed", extra={"document_id": document.document_id})
            raise IngestionFailed("Document ingestion failed; source retained for retry") from error
        return document, not existing or present != expected


@dataclass(slots=True)
class ListDocuments:
    repository: DocumentRepository

    def execute(self) -> list[Document]:
        return self.repository.list()


@dataclass(slots=True)
class DeleteDocument:
    repository: DocumentRepository
    store: KnowledgeStore
    lock: Callable[[], AbstractContextManager[None]] = nullcontext

    def execute(self, document_id: str) -> None:
        with self.lock():
            try:
                self.repository.get(document_id)
            except DocumentCorrupt:
                pass  # Explicit delete is also recovery for a partial source directory.
            except DocumentNotFound:
                if not self.store.document_chunk_ids(document_id):
                    raise
            self.store.delete_document(document_id)
            try:
                self.repository.delete(document_id)
            except DocumentNotFound:
                pass
