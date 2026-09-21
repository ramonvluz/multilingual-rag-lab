from __future__ import annotations

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

    def execute(self, spec: IndexSpec) -> int:
        """Build a candidate collection and atomically promote it only after validation."""
        collection = self.store.create_collection(spec)
        indexed = 0
        try:
            for document in self.repository.list():
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
            if self.store.count(collection) != indexed:
                raise IngestionFailed("Candidate collection validation failed")
            self.store.promote(collection)
            self.manifest.save(IndexManifest(spec, collection))
            return indexed
        except Exception:
            # The active alias and previous manifest are deliberately untouched.
            raise
