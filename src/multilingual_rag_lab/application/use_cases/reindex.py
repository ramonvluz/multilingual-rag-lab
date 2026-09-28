from __future__ import annotations

from collections.abc import Callable
from contextlib import AbstractContextManager, nullcontext
from dataclasses import dataclass
from typing import Any

from multilingual_rag_lab.application.ports import (
    Chunker,
    DocumentParser,
    DocumentRepository,
    Embedder,
)
from multilingual_rag_lab.domain import FileIndexManifest, IndexManifest
from multilingual_rag_lab.domain.errors import IngestionFailed
from multilingual_rag_lab.domain.models import IndexSpec


@dataclass(slots=True)
class ReindexCorpus:
    repository: DocumentRepository
    parser: DocumentParser
    chunker: Chunker
    embedder: Embedder
    store: Any
    manifest: FileIndexManifest
    lock: Callable[[], AbstractContextManager[None]] = nullcontext

    def execute(self, spec: IndexSpec) -> int:
        with self.lock():
            return self._execute(spec)

    def _execute(self, spec: IndexSpec) -> int:
        previous = self.store.active_collection()
        collection = self.store.create_collection(spec)
        indexed = 0
        expected: set[str] = set()
        promotion_attempted = False
        try:
            documents = self.repository.list()
            for document in documents:
                parsed = self.parser.parse(
                    self.repository.source_path(document), document.file_type
                )
                chunks = self.chunker.chunk(document.document_id, parsed)
                if not chunks:
                    raise IngestionFailed(f"No chunks extracted for {document.document_id}")
                self.store.upsert_into(
                    collection, chunks, self.embedder.embed([item.text for item in chunks])
                )
                indexed += len(chunks)
                expected.update(chunk.chunk_id for chunk in chunks)
            self.store.validate_contents(
                spec, collection, {d.document_id for d in documents}, expected
            )
            promotion_attempted = True
            self.store.promote(collection)
            self.manifest.save(IndexManifest(spec, collection))
            return indexed
        except Exception as error:
            try:
                if promotion_attempted:
                    self.store.promote(previous)
                self.store.remove_candidate(collection)
            except Exception as recovery_error:
                raise IngestionFailed(
                    f"Reindex failed; recovery/cleanup failed for candidate {collection}; previous={previous}. Reconcile alias/manifest before retry"
                ) from recovery_error
            if isinstance(error, IngestionFailed):
                raise
            raise
