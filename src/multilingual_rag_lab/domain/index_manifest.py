from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path

from multilingual_rag_lab.domain.errors import IndexNotReady
from multilingual_rag_lab.domain.models import IndexSpec


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
        return IndexManifest(IndexSpec(**raw["spec"]), raw["collection_name"])

    def save(self, manifest: IndexManifest) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self.path.with_suffix(".tmp")
        temporary.write_text(
            json.dumps(
                {"spec": asdict(manifest.spec), "collection_name": manifest.collection_name},
                ensure_ascii=False,
                sort_keys=True,
            ),
            encoding="utf-8",
        )
        temporary.replace(self.path)
