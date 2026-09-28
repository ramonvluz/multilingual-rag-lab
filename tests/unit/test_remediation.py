import hashlib
import json
import logging
import subprocess
import sys
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace

import pytest

from multilingual_rag_lab.adapters.outbound.storage import FileSystemDocumentRepository
from multilingual_rag_lab.adapters.outbound.storage.locking import mutation_lock
from multilingual_rag_lab.adapters.outbound.vector_store import QdrantKnowledgeStore
from multilingual_rag_lab.bootstrap.composition import make_index_spec
from multilingual_rag_lab.bootstrap.logging import configure_logging
from multilingual_rag_lab.bootstrap.settings import Settings
from multilingual_rag_lab.domain.errors import DocumentCorrupt
from multilingual_rag_lab.domain.models import Document, SparseConfig
from multilingual_rag_lab.evaluation.retrieval import rrf_scores
from multilingual_rag_lab.evaluation.runner import retrieve_candidates


def test_index_identity_includes_materialization_configuration():
    spec = make_index_spec(Settings())
    assert spec == make_index_spec(Settings())
    assert spec.fingerprint == make_index_spec(Settings()).fingerprint
    for change in [
        replace(spec, chunk_size=256),
        replace(spec, sparse_config=replace(SparseConfig(), b=0.5)),
        replace(spec, tokenizer_revision="different"),
    ]:
        assert change.fingerprint != spec.fingerprint


def test_sparse_document_and_query_paths_are_distinct(monkeypatch):
    calls = []

    class Model:
        def __init__(self, **config):
            calls.append(config)

        def embed(self, texts):
            calls.append("document")
            return [SimpleNamespace(indices=[1], values=[2.0])]

        def query_embed(self, texts):
            calls.append("query")
            return [SimpleNamespace(indices=[1], values=[1.0])]

    monkeypatch.setitem(sys.modules, "fastembed", SimpleNamespace(SparseTextEmbedding=Model))
    store = QdrantKnowledgeStore(":memory:")
    assert store._sparse_vectors(["x"])[0].values == [2]
    assert store._sparse_vectors(["x"], query=True)[0].values == [1]
    assert calls[0]["disable_stemmer"] is True
    assert calls[0]["avg_len"] == 256 and calls[1:] == ["document", "query"]


def test_local_mutation_lock_excludes_second_process_and_releases(tmp_path):
    code = "from pathlib import Path; from multilingual_rag_lab.adapters.outbound.storage.locking import mutation_lock; import sys;\nwith mutation_lock(Path(sys.argv[1])): pass"
    with mutation_lock(tmp_path):
        result = subprocess.run(
            [sys.executable, "-B", "-c", code, str(tmp_path)], capture_output=True, text=True
        )
        assert result.returncode != 0 and "Another mutation" in result.stderr
    subprocess.run([sys.executable, "-B", "-c", code, str(tmp_path)], check=True)
    crash = "from pathlib import Path; from multilingual_rag_lab.adapters.outbound.storage.locking import mutation_lock; import sys,os;\nwith mutation_lock(Path(sys.argv[1])): os._exit(0)"
    subprocess.run([sys.executable, "-B", "-c", crash, str(tmp_path)], check=True)
    with mutation_lock(tmp_path):
        pass


@pytest.mark.parametrize(
    "fault", ["missing_source", "wrong_bytes", "missing_metadata", "bad_metadata"]
)
def test_repository_detects_partial_states(tmp_path, fault):
    repo = FileSystemDocumentRepository(tmp_path / "documents")
    doc = Document.from_content(b"evidence", "fixture.md", "md")
    source = repo.save(doc, b"evidence")
    if fault == "missing_source":
        source.unlink()
    elif fault == "wrong_bytes":
        source.write_bytes(b"wrong")
    elif fault == "missing_metadata":
        (source.parent / "metadata.json").unlink()
    else:
        (source.parent / "metadata.json").write_text("{invalid")
    with pytest.raises(DocumentCorrupt):
        repo.get(doc.document_id)
    with pytest.raises(DocumentCorrupt):
        repo.list()


def test_corpus_approved_bytes_cross_platform():
    root = Path(__file__).resolve().parents[2] / "data/corpus/v1.0.0"
    digest = hashlib.sha256(
        b"".join(
            p.relative_to(root).as_posix().encode() + b"\0" + p.read_bytes()
            for p in sorted(root.rglob("*"))
            if p.is_file()
        )
    ).hexdigest()
    assert digest == "8d8096d7284f4fb6629dce200dcd8402ae6f78c8779ad3339b56b51531c5612c"
    attributes = (root.parents[2] / ".gitattributes").read_text()
    assert "data/corpus/v1.0.0/** -text" in attributes


def test_logging_level_applied():
    configure_logging("DEBUG")
    assert logging.getLogger("multilingual_rag_lab").isEnabledFor(logging.DEBUG)
    configure_logging("WARNING")
    assert not logging.getLogger("multilingual_rag_lab").isEnabledFor(logging.INFO)
    configure_logging("INFO")


def test_cli_batch_failures_exit_nonzero(monkeypatch, capsys):
    from multilingual_rag_lab.adapters.inbound.cli import main as cli
    from multilingual_rag_lab.application.corpus import CorpusIngestionSummary

    monkeypatch.setattr(cli, "build_container", lambda: SimpleNamespace(ingest=None))
    monkeypatch.setattr(
        cli.IngestCorpus,
        "execute",
        lambda *a: CorpusIngestionSummary(24, 24, 23, 0, ("DOC-001: failed",)),
    )
    monkeypatch.setattr(sys, "argv", ["rag-lab", "ingest-corpus", "fixture"])
    with pytest.raises(SystemExit) as error:
        cli.main()
    assert error.value.code == 1
    assert json.loads(capsys.readouterr().out)["failures"]


def test_rrf_score_is_effective_ranking_score():
    from multilingual_rag_lab.domain.models import Chunk, RetrievedChunk

    item = RetrievedChunk(Chunk.create("doc", 0, "x"), 987)
    backend = SimpleNamespace(dense=lambda *a: [item], sparse=lambda *a: [item])
    result = retrieve_candidates(backend, "hybrid", "fixture", 30)
    assert result[0].score == pytest.approx(2 / 61)
    assert rrf_scores([[item.chunk.chunk_id] * 2]) == {item.chunk.chunk_id: 1 / 61}
