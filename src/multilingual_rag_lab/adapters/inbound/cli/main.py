from __future__ import annotations

import argparse
import hashlib
import json
import platform
from dataclasses import asdict
from importlib.metadata import version
from pathlib import Path

from multilingual_rag_lab.adapters.outbound.reranking import QwenReranker
from multilingual_rag_lab.adapters.outbound.storage import FileSystemDocumentRepository
from multilingual_rag_lab.application.corpus import IngestCorpus, validate_corpus
from multilingual_rag_lab.bootstrap.composition import build_container, build_reindex_use_case
from multilingual_rag_lab.bootstrap.settings import Settings
from multilingual_rag_lab.domain import FileIndexManifest
from multilingual_rag_lab.evaluation import (
    ExperimentalRetriever,
    load_dataset,
    run_retrieval_evaluation,
)
from multilingual_rag_lab.evaluation.document_ids import resolve_document_ids


def main() -> None:
    parser = argparse.ArgumentParser(prog="rag-lab")
    commands = parser.add_subparsers(dest="command", required=True)
    ingest = commands.add_parser("ingest")
    ingest.add_argument("file", type=Path)
    ingest_corpus = commands.add_parser("ingest-corpus")
    ingest_corpus.add_argument("corpus", type=Path)
    validate_corpus_command = commands.add_parser("validate-corpus")
    validate_corpus_command.add_argument("corpus", type=Path)
    commands.add_parser("reindex")
    evaluate = commands.add_parser("evaluate")
    evaluate.add_argument("dataset", type=Path)
    evaluate.add_argument(
        "--output", type=Path, default=Path("evaluation/results/retrieval-v1.json")
    )
    evaluate.add_argument("--corpus", type=Path, default=Path("data/corpus/v1.0.0"))
    evaluate.add_argument(
        "--top-k", type=int, default=10, help="Maximum document k (V1: at least 10)"
    )
    evaluate.add_argument(
        "--candidate-pool", type=int, default=30, help="Chunk candidates per dense/sparse branch"
    )
    evaluate.add_argument(
        "--validate-only",
        action="store_true",
        help="Validate Golden V1 and runtime mapping; no models, queries or report",
    )
    args = parser.parse_args()
    if args.command == "ingest":
        container = build_container()
        document, created = container.ingest.execute(args.file.name, args.file.read_bytes())
        print(json.dumps({"document_id": document.document_id, "created": created}))
    elif args.command == "ingest-corpus":
        container = build_container()
        summary = IngestCorpus(container.ingest).execute(args.corpus)
        print(json.dumps(asdict(summary)))
    elif args.command == "validate-corpus":
        corpus = validate_corpus(args.corpus)
        print(json.dumps({"root": str(corpus.root), "documents": len(corpus.documents)}))
    elif args.command == "reindex":
        use_case, spec = build_reindex_use_case()
        print(
            json.dumps({"indexed_chunks": use_case.execute(spec), "fingerprint": spec.fingerprint})
        )
    else:
        dataset = load_dataset(args.dataset)
        settings = Settings()
        if not (settings.runtime_dir / "documents").is_dir():
            parser.error("Operational documents directory is missing")
        repository = FileSystemDocumentRepository(settings.runtime_dir / "documents")
        document_ids = resolve_document_ids(args.corpus, repository)
        if args.validate_only:
            print(
                json.dumps(
                    {
                        "queries": len(dataset),
                        "answerable": sum(row["answerability"] == "answerable" for row in dataset),
                        "unanswerable": sum(
                            row["answerability"] == "unanswerable" for row in dataset
                        ),
                        "mapped_documents": len(document_ids),
                    }
                )
            )
            return
        if args.top_k < 10 or args.candidate_pool < args.top_k:
            parser.error("V1 requires --top-k >= 10 and --candidate-pool >= --top-k")
        if args.output.exists():
            parser.error("Output already exists; choose a new result path")
        container = build_container(settings)
        index_manifest = FileIndexManifest(settings.runtime_dir / "index" / "manifest.json").load()
        if index_manifest.spec != container.index_spec:
            parser.error("Active IndexSpec differs from evaluation configuration")
        client = container.store._get_client()
        active = {alias.alias_name: alias.collection_name for alias in client.get_aliases().aliases}
        if active.get(container.store.alias_name) != index_manifest.collection_name:
            parser.error("Active Qdrant alias differs from the persisted manifest")
        manifest_path = args.corpus / "manifest.json"
        corpus_manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        provenance = {
            "dataset": str(args.dataset),
            "dataset_version": "golden_v1",
            "dataset_sha256": hashlib.sha256(args.dataset.read_bytes()).hexdigest(),
            "corpus_version": corpus_manifest["corpus_version"],
            "corpus_manifest_sha256": hashlib.sha256(manifest_path.read_bytes()).hexdigest(),
            "collection": index_manifest.collection_name,
            "alias": container.store.alias_name,
            "indexed_points": container.store.count(index_manifest.collection_name),
            "device": settings.embedding_device,
            "python": platform.python_version(),
            "platform": platform.platform(),
            "packages": {
                name: version(name)
                for name in (
                    "multilingual-rag-lab",
                    "qdrant-client",
                    "fastembed",
                    "sentence-transformers",
                    "torch",
                    "transformers",
                )
            },
        }
        reports = {}
        for variant in ("dense", "hybrid", "hybrid_rerank"):
            reranker = (
                QwenReranker(device=container.settings.embedding_device)
                if variant == "hybrid_rerank"
                else None
            )
            backend = ExperimentalRetriever(container.query.embedder, container.store, reranker)
            reports[variant] = run_retrieval_evaluation(
                dataset,
                backend,
                variant,
                document_ids,
                index_manifest.spec,
                max_document_k=args.top_k,
                candidate_pool=args.candidate_pool,
                provenance=provenance,
            )
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(reports, ensure_ascii=False, indent=2), encoding="utf-8")
        print(json.dumps({"report": str(args.output), "variants": list(reports)}))
