from __future__ import annotations

import hashlib
from collections import defaultdict
from pathlib import Path

from multilingual_rag_lab.application.corpus import validate_corpus
from multilingual_rag_lab.application.ports import DocumentRepository
from multilingual_rag_lab.domain.models import Document
from multilingual_rag_lab.evaluation.dataset import OFFICIAL_DOCUMENT_IDS


def resolve_document_ids(corpus_root: Path, repository: DocumentRepository) -> dict[str, str]:
    """Resolve all 24 official files to SHA -> DOC, checking source identity read-only."""
    corpus = validate_corpus(corpus_root)
    if {entry["document_id"] for entry, _ in corpus.documents} != OFFICIAL_DOCUMENT_IDS:
        raise ValueError("Manifest must identify DOC-001 through DOC-024 unambiguously")
    by_filename: dict[str, list[Document]] = defaultdict(list)
    for document in repository.list():
        by_filename[document.filename].append(document)
    mapping: dict[str, str] = {}
    for entry, path in corpus.documents:
        matches = by_filename[path.name]
        stable_id = str(entry["document_id"])
        if len(matches) != 1:
            raise ValueError(
                f"{stable_id} ({path.name}): expected one operational document; found {len(matches)} (missing/ambiguous mapping)"
            )
        document = matches[0]
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        source = repository.source_path(document)
        if not source.is_file():
            raise ValueError(f"{stable_id}: operational source is missing")
        if (
            document.document_id != digest
            or document.content_hash != digest
            or hashlib.sha256(source.read_bytes()).hexdigest() != digest
        ):
            raise ValueError(
                f"{stable_id}: operational SHA/source differs from the official corpus"
            )
        if digest in mapping:
            raise ValueError(f"{stable_id}: ambiguous SHA shared with {mapping[digest]}")
        mapping[digest] = stable_id
    return mapping
