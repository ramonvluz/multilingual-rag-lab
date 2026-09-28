from __future__ import annotations

import json
import os
import tempfile
from dataclasses import asdict, dataclass
from pathlib import Path

from multilingual_rag_lab.domain.errors import IndexNotReady
from multilingual_rag_lab.domain.models import IndexSpec, SparseConfig


@dataclass(frozen=True, slots=True)
class IndexManifest:
    spec: IndexSpec
    collection_name: str


class FileIndexManifest:
    def __init__(self, path: Path) -> None:
        self.path = path

    def load(self) -> IndexManifest:
        try:
            raw = json.loads(self.path.read_text(encoding="utf-8"))
        except FileNotFoundError as error:
            raise IndexNotReady("No active index manifest; run `rag-lab reindex`") from error
        spec = raw["spec"]
        if spec.get("sparse_config") is not None:
            spec["sparse_config"] = SparseConfig(**spec["sparse_config"])
        return IndexManifest(IndexSpec(**spec), raw["collection_name"])

    def save(self, manifest: IndexManifest) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        atomic_json(
            self.path, {"spec": asdict(manifest.spec), "collection_name": manifest.collection_name}
        )


def atomic_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, name = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
    temporary = Path(name)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            json.dump(value, stream, ensure_ascii=False, sort_keys=True)
            stream.flush()
            os.fsync(stream.fileno())
        temporary.replace(path)
    finally:
        temporary.unlink(missing_ok=True)
