import json
from pathlib import Path

import pytest

from multilingual_rag_lab.application.corpus import (
    CorpusValidationError,
    IngestCorpus,
    ValidatedCorpus,
    validate_corpus,
)
from multilingual_rag_lab.domain.errors import UnsupportedDocument


def write_corpus(root: Path, filename: str = "DOC-001_fixture.md") -> Path:
    documents = root / "documents"
    documents.mkdir(parents=True)
    (documents / filename).write_text("fixture", encoding="utf-8")
    (root / "manifest.json").write_text(
        json.dumps(
            {"documents": [{"document_id": "DOC-001", "filename": filename, "format": "md"}]}
        ),
        encoding="utf-8",
    )
    return root


def test_valid_manifest_returns_declared_document(tmp_path: Path) -> None:
    corpus = validate_corpus(write_corpus(tmp_path), expected_count=1)
    assert corpus.documents[0][0]["document_id"] == "DOC-001"


def test_manifest_missing_document_stops_validation(tmp_path: Path) -> None:
    root = write_corpus(tmp_path)
    (root / "documents" / "DOC-001_fixture.md").unlink()
    with pytest.raises(CorpusValidationError, match="missing"):
        validate_corpus(root, expected_count=1)


def test_unsupported_manifest_format_stops_validation(tmp_path: Path) -> None:
    root = write_corpus(tmp_path, "DOC-001_fixture.exe")
    data = json.loads((root / "manifest.json").read_text(encoding="utf-8"))
    data["documents"][0]["format"] = "exe"
    (root / "manifest.json").write_text(json.dumps(data), encoding="utf-8")
    with pytest.raises(UnsupportedDocument):
        validate_corpus(root, expected_count=1)


def test_unregistered_document_stops_validation(tmp_path: Path) -> None:
    root = write_corpus(tmp_path)
    (root / "documents" / "DOC-999_extra.md").write_text("extra", encoding="utf-8")
    with pytest.raises(CorpusValidationError, match="unregistered"):
        validate_corpus(root, expected_count=1)


class IngestSpy:
    def __init__(self) -> None:
        self.calls: list[tuple[str, bytes]] = []

    def execute(self, filename: str, content: bytes) -> tuple[object, bool]:
        self.calls.append((filename, content))
        return object(), len(self.calls) == 1


def test_batch_ingestion_uses_ingest_document_and_is_idempotent(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    path = tmp_path / "DOC-001_fixture.md"
    path.write_text("fixture", encoding="utf-8")
    corpus = ValidatedCorpus(tmp_path, (({"document_id": "DOC-001"}, path),))
    monkeypatch.setattr("multilingual_rag_lab.application.corpus.validate_corpus", lambda root: corpus)
    spy = IngestSpy()
    first = IngestCorpus(spy).execute(tmp_path)
    second = IngestCorpus(spy).execute(tmp_path)
    assert first.ingested == 1 and first.already_present == 0 and not first.failures
    assert second.ingested == 0 and second.already_present == 1 and not second.failures
    assert [name for name, _ in spy.calls] == [path.name, path.name]


def test_batch_summary_reports_document_failures(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    path = tmp_path / "DOC-001_fixture.md"
    path.write_text("fixture", encoding="utf-8")
    corpus = ValidatedCorpus(tmp_path, (({"document_id": "DOC-001"}, path),))
    monkeypatch.setattr("multilingual_rag_lab.application.corpus.validate_corpus", lambda root: corpus)

    class FailingIngest:
        def execute(self, filename: str, content: bytes) -> tuple[object, bool]:
            raise UnsupportedDocument("unsupported")

    summary = IngestCorpus(FailingIngest()).execute(tmp_path)
    assert summary.ingested == 0 and summary.already_present == 0
    assert summary.failures == ("DOC-001: unsupported",)
