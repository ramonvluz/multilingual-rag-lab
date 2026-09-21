from __future__ import annotations

import json
import shutil
from dataclasses import asdict
from datetime import datetime
from pathlib import Path

from multilingual_rag_lab.domain.errors import DocumentNotFound
from multilingual_rag_lab.domain.models import Document


class FileSystemDocumentRepository:
    def __init__(self, root: Path) -> None:
        self.root = root
        self.root.mkdir(parents=True, exist_ok=True)

    def save(self, document: Document, content: bytes) -> Path:
        directory = self.root / document.document_id
        directory.mkdir(parents=True, exist_ok=True)
        source = directory / f"source.{document.file_type}"
        source.write_bytes(content)
        metadata = asdict(document)
        metadata["ingested_at"] = document.ingested_at.isoformat()
        (directory / "metadata.json").write_text(
            json.dumps(metadata, ensure_ascii=False), encoding="utf-8"
        )
        return source

    def _load(self, directory: Path) -> Document:
        try:
            value = json.loads((directory / "metadata.json").read_text(encoding="utf-8"))
            value["ingested_at"] = datetime.fromisoformat(value["ingested_at"])
            return Document(**value)
        except FileNotFoundError as error:
            raise DocumentNotFound(f"Document {directory.name} was not found") from error

    def get(self, document_id: str) -> Document:
        return self._load(self.root / document_id)

    def list(self) -> list[Document]:
        return [
            self._load(path)
            for path in self.root.iterdir()
            if path.is_dir() and (path / "metadata.json").exists()
        ]

    def delete(self, document_id: str) -> None:
        directory = self.root / document_id
        if not directory.exists():
            raise DocumentNotFound(f"Document {document_id} was not found")
        shutil.rmtree(directory)

    def source_path(self, document: Document) -> Path:
        return self.root / document.document_id / f"source.{document.file_type}"
