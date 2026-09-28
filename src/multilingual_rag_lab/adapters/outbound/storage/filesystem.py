from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import tempfile
from dataclasses import asdict
from datetime import datetime
from pathlib import Path

from multilingual_rag_lab.domain.errors import DocumentCorrupt, DocumentNotFound
from multilingual_rag_lab.domain.index_manifest import atomic_json
from multilingual_rag_lab.domain.models import Document


class FileSystemDocumentRepository:
    def __init__(self, root: Path) -> None:
        self.root = root
        self.root.mkdir(parents=True, exist_ok=True)

    def save(self, document: Document, content: bytes) -> Path:
        directory = self._directory(document.document_id)
        if hashlib.sha256(content).hexdigest() != document.document_id:
            raise DocumentCorrupt("Source bytes do not match document identity")
        directory.mkdir(parents=True, exist_ok=True)
        source = directory / f"source.{document.file_type}"
        fd, name = tempfile.mkstemp(prefix=".source.", dir=directory)
        temporary = Path(name)
        try:
            with os.fdopen(fd, "wb") as stream:
                stream.write(content)
                stream.flush()
                os.fsync(stream.fileno())
            temporary.replace(source)
        finally:
            temporary.unlink(missing_ok=True)
        self.save_metadata(document)
        return source

    def _directory(self, document_id: str) -> Path:
        if re.fullmatch(r"[a-f0-9]{64}", document_id) is None:
            raise DocumentNotFound("Invalid document ID")
        directory = self.root / document_id
        if directory.is_symlink():
            raise DocumentCorrupt("Symlink document directory is not supported")
        return directory

    def save_metadata(self, document: Document) -> None:
        metadata = asdict(document)
        metadata["ingested_at"] = document.ingested_at.isoformat()
        atomic_json(self._directory(document.document_id) / "metadata.json", metadata)

    def _load(self, directory: Path) -> Document:
        try:
            value = json.loads((directory / "metadata.json").read_text(encoding="utf-8"))
            value["ingested_at"] = datetime.fromisoformat(value["ingested_at"])
            document = Document(**value)
            if (
                document.document_id != directory.name
                or document.content_hash != directory.name
                or Path(document.filename).name != document.filename
                or "\\" in document.filename
                or document.file_type not in {"md", "html", "docx", "pdf", "csv", "xlsx"}
            ):
                raise ValueError("Invalid metadata")
            source = self.source_path(document)
            if (
                source.is_symlink()
                or hashlib.sha256(source.read_bytes()).hexdigest() != document.content_hash
            ):
                raise ValueError("Source hash mismatch")
            return document
        except (FileNotFoundError, ValueError, TypeError, KeyError) as error:
            if not directory.exists():
                raise DocumentNotFound(f"Document {directory.name} was not found") from error
            raise DocumentCorrupt(
                f"Incomplete/corrupt document {directory.name}; repair or delete explicitly"
            ) from error

    def get(self, document_id: str) -> Document:
        return self._load(self._directory(document_id))

    def list(self) -> list[Document]:
        return [self.get(path.name) for path in self.root.iterdir() if path.is_dir()]

    def delete(self, document_id: str) -> None:
        directory = self._directory(document_id)
        if not directory.exists():
            raise DocumentNotFound(f"Document {document_id} was not found")
        shutil.rmtree(directory)

    def source_path(self, document: Document) -> Path:
        return self._directory(document.document_id) / f"source.{document.file_type}"
