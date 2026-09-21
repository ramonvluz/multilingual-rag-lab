from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from multilingual_rag_lab.application.use_cases.documents import SUPPORTED_TYPES, IngestDocument
from multilingual_rag_lab.domain.errors import (
    ApplicationError,
    IngestionFailed,
    UnsupportedDocument,
)

EXPECTED_CORPUS_DOCUMENT_COUNT = 24


class CorpusValidationError(IngestionFailed):
    """The versioned corpus structure does not match its declared manifest."""


@dataclass(frozen=True, slots=True)
class ValidatedCorpus:
    root: Path
    documents: tuple[tuple[dict[str, Any], Path], ...]


@dataclass(frozen=True, slots=True)
class CorpusIngestionSummary:
    total_found: int
    total_validated: int
    ingested: int
    already_present: int
    failures: tuple[str, ...] = field(default_factory=tuple)


def validate_corpus(root: Path, expected_count: int = EXPECTED_CORPUS_DOCUMENT_COUNT) -> ValidatedCorpus:
    manifest_path = root / "manifest.json"
    documents_dir = root / "documents"
    if not manifest_path.is_file():
        raise CorpusValidationError("Corpus manifest.json is missing")
    if not documents_dir.is_dir():
        raise CorpusValidationError("Corpus documents directory is missing")
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as error:
        raise CorpusValidationError("Corpus manifest.json is not valid JSON") from error
    entries = manifest.get("documents")
    if not isinstance(entries, list):
        raise CorpusValidationError("Corpus manifest must contain a documents list")
    if len(entries) != expected_count:
        raise CorpusValidationError(
            f"Corpus manifest declares {len(entries)} documents; expected {expected_count}"
        )
    declared_names: set[str] = set()
    declared_ids: set[str] = set()
    validated: list[tuple[dict[str, Any], Path]] = []
    for entry in entries:
        if not isinstance(entry, dict):
            raise CorpusValidationError("Corpus manifest has a non-object document entry")
        filename = entry.get("filename")
        document_id = entry.get("document_id")
        file_format = entry.get("format")
        if (
            not isinstance(filename, str)
            or not filename
            or not isinstance(document_id, str)
            or not document_id
            or not isinstance(file_format, str)
            or not file_format
        ):
            raise CorpusValidationError("Each corpus document requires document_id, filename, and format")
        if Path(filename).name != filename or filename in declared_names:
            raise CorpusValidationError(f"Invalid or duplicate corpus filename: {filename}")
        if document_id in declared_ids or not filename.startswith(f"{document_id}_"):
            raise CorpusValidationError(f"Inconsistent corpus document ID and filename: {document_id}")
        suffix = Path(filename).suffix.lower().lstrip(".")
        if suffix not in SUPPORTED_TYPES or suffix != file_format.lower():
            raise UnsupportedDocument(f"Unsupported corpus format for {filename}")
        path = documents_dir / filename
        if not path.is_file():
            raise CorpusValidationError(f"Corpus document declared in manifest is missing: {filename}")
        declared_names.add(filename)
        declared_ids.add(document_id)
        validated.append((entry, path))
    actual_names = {path.name for path in documents_dir.rglob("*") if path.is_file()}
    extras = actual_names - declared_names
    if extras:
        raise CorpusValidationError(f"Corpus documents directory has unregistered files: {sorted(extras)}")
    if len(actual_names) != expected_count:
        raise CorpusValidationError(
            f"Corpus documents directory has {len(actual_names)} files; expected {expected_count}"
        )
    return ValidatedCorpus(root, tuple(validated))


@dataclass(slots=True)
class IngestCorpus:
    ingest_document: IngestDocument

    def execute(self, root: Path) -> CorpusIngestionSummary:
        corpus = validate_corpus(root)
        ingested = 0
        present = 0
        failures: list[str] = []
        for entry, path in corpus.documents:
            try:
                _, created = self.ingest_document.execute(path.name, path.read_bytes())
            except ApplicationError as error:
                failures.append(f"{entry['document_id']}: {error}")
                continue
            if created:
                ingested += 1
            else:
                present += 1
        return CorpusIngestionSummary(
            total_found=len(corpus.documents),
            total_validated=len(corpus.documents),
            ingested=ingested,
            already_present=present,
            failures=tuple(failures),
        )
