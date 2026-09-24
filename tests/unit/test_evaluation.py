import copy
import json
import math
from collections import Counter
from pathlib import Path

import pytest

from multilingual_rag_lab.adapters.outbound.storage import FileSystemDocumentRepository
from multilingual_rag_lab.domain.models import Chunk, Document, IndexSpec, RetrievedChunk
from multilingual_rag_lab.evaluation.dataset import (
    GOLDEN_V1_DISTRIBUTION,
    load_dataset,
    validate_dataset,
)
from multilingual_rag_lab.evaluation.document_ids import resolve_document_ids
from multilingual_rag_lab.evaluation.metrics import ndcg_at_k, recall_at_k, reciprocal_rank
from multilingual_rag_lab.evaluation.reporting import latency_summary
from multilingual_rag_lab.evaluation.retrieval import reciprocal_rank_fusion
from multilingual_rag_lab.evaluation.runner import (
    WARMUP_QUERY,
    document_ranking,
    run_retrieval_evaluation,
)

ROOT = Path(__file__).resolve().parents[2]
SPEC = IndexSpec("fixture", 2, "cosine", "fixture", "v1", "qdrant-bm25-v1")
MAPPING = {"sha1": "DOC-001", "sha2": "DOC-002", "sha3": "DOC-003"}


def row(query_id="fixture-1", kind="multi_context", language="en", relevant=None):
    return {
        "query_id": query_id,
        "query": "fixture query",
        "primary_type": kind,
        "query_language": language,
        "tags": ["multi_document"],
        "answerability": "answerable",
        "relevant_documents": relevant or ["DOC-001", "DOC-002"],
        "reference_answer": "fixture reference",
        "notes": "fixture note",
    }


def test_official_golden_v1_loader():
    rows = load_dataset(ROOT / "evaluation/datasets/golden_v1.jsonl")
    assert len(rows) == 48
    assert {r["query_id"] for r in rows} == {f"Q-{n:03d}" for n in range(1, 49)}
    assert Counter(r["primary_type"] for r in rows) == GOLDEN_V1_DISTRIBUTION
    assert Counter(r["answerability"] for r in rows) == {"answerable": 44, "unanswerable": 4}


@pytest.mark.parametrize(
    "mutation,match",
    [
        (lambda rows: rows[0].pop("primary_type"), "schema"),
        (lambda rows: rows[0].update(relevant_documents=["DOC-999"]), "DOC IDs"),
        (lambda rows: rows[0].update(tags="invalid"), "string list"),
        (lambda rows: rows[0].update(answerability="unknown"), "answerability"),
        (lambda rows: rows[0].update(relevant_documents=[]), "answerability"),
        (lambda rows: rows.append(copy.deepcopy(rows[0])), "duplicate"),
    ],
)
def test_schema_rejects_invalid_rows(mutation, match):
    rows = [row()]
    mutation(rows)
    with pytest.raises(ValueError, match=match):
        validate_dataset(rows)


@pytest.mark.parametrize(
    "change,match",
    [
        (lambda rows: rows.pop(), "exactly"),
        (lambda rows: rows[0].update(primary_type="exact"), "distribution"),
        (lambda rows: rows[0].update(query_id="Q-999"), "exactly"),
    ],
)
def test_official_loader_rejects_invalid_distribution_or_ids(tmp_path, change, match):
    rows = load_dataset(ROOT / "evaluation/datasets/golden_v1.jsonl")
    change(rows)
    path = tmp_path / "invalid.jsonl"
    path.write_text("\n".join(json.dumps(r) for r in rows), encoding="utf-8")
    with pytest.raises(ValueError, match=match):
        load_dataset(path)


def test_rrf_fuses_rankings_deterministically() -> None:
    assert reciprocal_rank_fusion([["a", "b"], ["b", "a"]]) == ["a", "b"]


def test_retrieval_metrics() -> None:
    retrieved, relevant = ["a", "b", "c"], {"b", "z"}
    assert recall_at_k(retrieved, relevant, 2) == 0.5
    assert reciprocal_rank(retrieved, relevant) == 0.5
    assert 0 < ndcg_at_k(retrieved, relevant, 3) < 1


class Backend:
    def __init__(self):
        self.calls = []
        self.clock = 0.0
        self.dense_items = [
            RetrievedChunk(Chunk.create("sha1", i, f"duplicate {i}"), 1.0) for i in range(12)
        ] + [RetrievedChunk(Chunk.create("sha2", 0, "second"), 0.5)]
        self.sparse_items = [RetrievedChunk(Chunk.create("sha3", 0, "third"), 0.8)]

    def tick(self, stage, query, limit):
        self.calls.append((stage, query, limit))
        self.clock += 100 if query == WARMUP_QUERY else 0.01

    def dense(self, query: str, limit: int) -> list[RetrievedChunk]:
        self.tick("dense", query, limit)
        return self.dense_items[:limit]

    def sparse(self, query: str, limit: int) -> list[RetrievedChunk]:
        self.tick("sparse", query, limit)
        return self.sparse_items[:limit]

    def rerank(
        self, query: str, candidates: list[RetrievedChunk], limit: int
    ) -> list[RetrievedChunk]:
        self.tick("rerank", query, limit)
        self.last_reranked = candidates
        return list(reversed(candidates))[:limit]


@pytest.mark.parametrize(
    "variant,stages",
    [
        ("dense", ["dense"]),
        ("hybrid", ["dense", "sparse"]),
        ("hybrid_rerank", ["dense", "sparse", "rerank"]),
    ],
)
def test_variants_deduplicate_after_full_candidate_pool_and_warmup(monkeypatch, variant, stages):
    backend = Backend()
    monkeypatch.setattr(
        "multilingual_rag_lab.evaluation.runner.time.perf_counter", lambda: backend.clock
    )
    report = run_retrieval_evaluation([row()], backend, variant, MAPPING, SPEC)
    assert [call[0] for call in backend.calls] == stages * 2
    assert all(call[1] == WARMUP_QUERY for call in backend.calls[: len(stages)])
    assert all(call[2] == 30 for call in backend.calls if call[0] != "rerank")
    if variant == "dense":
        expected = ["DOC-001", "DOC-002"]
    else:
        candidates = {i.chunk.chunk_id: i for i in [*backend.dense_items, *backend.sparse_items]}
        ranks = reciprocal_rank_fusion(
            [
                [i.chunk.chunk_id for i in backend.dense_items],
                [i.chunk.chunk_id for i in backend.sparse_items],
            ]
        )
        fused = [candidates[key] for key in ranks]
        if variant == "hybrid_rerank":
            assert backend.last_reranked == fused
            assert backend.calls[-1][2] == 14  # rerank all candidates, not top-10 chunks
            fused.reverse()
        expected = document_ranking(fused, MAPPING)
    result = report["queries"][0]
    assert result["retrieved_documents"] == expected
    assert result["metrics"]["recall_at_3"] == 1
    assert result["metrics"]["recall_at_1"] == 0.5
    assert result["latency_ms"] == pytest.approx(len(stages) * 10)
    assert report["metadata"]["warmup_policy"]["model_initialization_excluded"] is True
    assert report["metadata"]["index_fingerprint"] == SPEC.fingerprint
    assert result["notes"] == "fixture note"
    assert result["tags"] == ["multi_document"]


def test_document_metrics_binary_multidocument_and_no_duplicates():
    ranking = ["a", "a", "x", "b", "b"]
    assert recall_at_k(ranking, {"a", "b"}, 1) == 0.5
    assert recall_at_k(ranking, {"a", "b"}, 3) == 1
    expected = (1 + 1 / math.log2(4)) / (1 + 1 / math.log2(3))
    assert ndcg_at_k(ranking, {"a", "b"}, 5) == pytest.approx(expected)
    assert ndcg_at_k(ranking, {"a", "b"}, 10) == pytest.approx(expected)
    assert ndcg_at_k(["a"] * 20, {"a"}, 10) == 1
    at_six = [str(n) for n in range(5)] + ["a"]
    assert ndcg_at_k(at_six, {"a"}, 5) == 0
    assert ndcg_at_k(at_six, {"a"}, 10) == pytest.approx(1 / math.log2(7))
    assert recall_at_k(at_six, {"a"}, 5) == 0
    assert reciprocal_rank(["x"] * 20 + ["a"], {"a"}, 10) == 0.5
    assert reciprocal_rank([str(n) for n in range(9)] + ["a"], {"a"}, 10) == 0.1
    assert reciprocal_rank([str(n) for n in range(10)] + ["a"], {"a"}, 10) == 0
    assert recall_at_k([], set(), 5) == ndcg_at_k([], set(), 10) == 0


def test_unanswerable_excluded_and_grouping_macro_averages():
    gap = {**row("gap", "unanswerable"), "answerability": "unanswerable", "relevant_documents": []}
    report = run_retrieval_evaluation(
        [row(), row("fixture-2", "semantic", "es", ["DOC-003"]), gap],
        Backend(),
        "dense",
        MAPPING,
        SPEC,
    )
    assert report["aggregate"]["query_count"] == 3
    assert report["aggregate"]["positive_query_count"] == 2
    assert report["aggregate"]["unanswerable_count"] == 1
    assert report["aggregate"]["metrics"]["recall_at_5"] == 0.5
    assert report["by_primary_type"]["multi_context"]["metrics"]["recall_at_5"] == 1
    assert report["by_query_language"]["es"]["metrics"]["recall_at_5"] == 0
    assert report["by_primary_type"]["unanswerable"]["metrics"]["ndcg_at_10"] is None
    assert report["queries"][-1]["metrics"] is None
    assert report["queries"][-1]["latency_ms"] is None
    assert report["queries"][-1]["status"] == "deferred_to_grounded_generation"


def test_latency_statistics():
    assert latency_summary([10, 20, 30, 40]) == {"mean": 25, "p50": 25, "p95": 38.5}
    assert latency_summary([7]) == {"mean": 7, "p50": 7, "p95": 7}
    assert latency_summary([]) == {"mean": None, "p50": None, "p95": None}


def test_unknown_ids_and_invalid_settings_fail_before_scoring():
    with pytest.raises(ValueError, match="not mapped"):
        document_ranking([RetrievedChunk(Chunk.create("unknown", 0, "x"), 1)], MAPPING)
    backend = Backend()
    with pytest.raises(ValueError, match="missing from manifest"):
        run_retrieval_evaluation([row(relevant=["DOC-024"])], backend, "dense", MAPPING, SPEC)
    assert backend.calls == []
    with pytest.raises(ValueError, match="Unknown retrieval variant"):
        run_retrieval_evaluation([row()], backend, "wrong", MAPPING, SPEC)
    with pytest.raises(ValueError, match="max_document_k"):
        run_retrieval_evaluation([row()], backend, "dense", MAPPING, SPEC, candidate_pool=5)


@pytest.fixture
def mapped_corpus(tmp_path):
    corpus = tmp_path / "corpus"
    (corpus / "documents").mkdir(parents=True)
    repository = FileSystemDocumentRepository(tmp_path / "runtime" / "documents")
    entries = []
    for n in range(1, 25):
        stable_id = f"DOC-{n:03d}"
        filename = f"{stable_id}_fixture.md"
        content = f"Fixture {n}".encode()
        (corpus / "documents" / filename).write_bytes(content)
        repository.save(Document.from_content(content, filename, "md"), content)
        entries.append({"document_id": stable_id, "filename": filename, "format": "md"})
    (corpus / "manifest.json").write_text(json.dumps({"documents": entries}), encoding="utf-8")
    return corpus, repository


def test_resolve_all_24_documents_from_manifest_and_filesystem(mapped_corpus):
    corpus, repository = mapped_corpus
    mapping = resolve_document_ids(corpus, repository)
    assert len(mapping) == 24
    for doc in repository.list():
        assert mapping[doc.document_id] == doc.filename.split("_")[0]


@pytest.mark.parametrize("failure", ["missing", "ambiguous", "changed_source", "wrong_manifest"])
def test_mapping_fails_closed(mapped_corpus, failure):
    corpus, repository = mapped_corpus
    doc = repository.list()[0]
    if failure == "missing":
        repository.delete(doc.document_id)
    elif failure == "ambiguous":
        other = Document.from_content(b"another revision", doc.filename, "md")
        repository.save(other, b"another revision")
    elif failure == "changed_source":
        repository.source_path(doc).write_bytes(b"corrupt")
    else:
        manifest = json.loads((corpus / "manifest.json").read_text())
        manifest["documents"][0]["document_id"] = "DOC-999"
        manifest["documents"][0]["filename"] = "DOC-999_fixture.md"
        (corpus / "documents" / "DOC-001_fixture.md").rename(
            corpus / "documents" / "DOC-999_fixture.md"
        )
        (corpus / "manifest.json").write_text(json.dumps(manifest))
    with pytest.raises(ValueError):
        resolve_document_ids(corpus, repository)


def test_validate_only_cli_never_builds_retrieval_backend(
    mapped_corpus, monkeypatch, capsys, tmp_path
):
    import sys

    from multilingual_rag_lab.adapters.inbound.cli import main as cli
    from multilingual_rag_lab.bootstrap.settings import Settings

    corpus, repository = mapped_corpus
    monkeypatch.setattr(cli, "Settings", lambda: Settings(runtime_dir=repository.root.parent))

    def forbidden(*args, **kwargs):
        pytest.fail("validate-only must not build container, load models or execute retrieval")

    monkeypatch.setattr(cli, "build_container", forbidden)
    monkeypatch.setattr(cli, "run_retrieval_evaluation", forbidden)
    output = tmp_path / "must-not-exist.json"
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "rag-lab",
            "evaluate",
            str(ROOT / "evaluation/datasets/golden_v1.jsonl"),
            "--corpus",
            str(corpus),
            "--validate-only",
            "--output",
            str(output),
        ],
    )
    cli.main()
    assert json.loads(capsys.readouterr().out) == {
        "queries": 48,
        "answerable": 44,
        "unanswerable": 4,
        "mapped_documents": 24,
    }
    assert not output.exists()
