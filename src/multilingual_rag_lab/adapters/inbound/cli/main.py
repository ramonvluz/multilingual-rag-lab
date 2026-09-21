from __future__ import annotations

import argparse
import json
from pathlib import Path

from multilingual_rag_lab.adapters.outbound.reranking import QwenReranker
from multilingual_rag_lab.bootstrap.composition import build_container, build_reindex_use_case
from multilingual_rag_lab.evaluation import (
    ExperimentalRetriever,
    load_dataset,
    run_retrieval_evaluation,
)


def main() -> None:
    parser = argparse.ArgumentParser(prog="rag-lab")
    commands = parser.add_subparsers(dest="command", required=True)
    ingest = commands.add_parser("ingest")
    ingest.add_argument("file", type=Path)
    commands.add_parser("reindex")
    evaluate = commands.add_parser("evaluate")
    evaluate.add_argument("dataset", type=Path)
    evaluate.add_argument("--output", type=Path, default=Path("runtime/evaluation-report.json"))
    evaluate.add_argument("--top-k", type=int, default=5)
    args = parser.parse_args()
    if args.command == "ingest":
        container = build_container()
        document, created = container.ingest.execute(args.file.name, args.file.read_bytes())
        print(json.dumps({"document_id": document.document_id, "created": created}))
    elif args.command == "reindex":
        use_case, spec = build_reindex_use_case()
        print(
            json.dumps({"indexed_chunks": use_case.execute(spec), "fingerprint": spec.fingerprint})
        )
    else:
        container = build_container()
        dataset = load_dataset(args.dataset)
        reports = {}
        for variant in ("dense", "hybrid", "hybrid_rerank"):
            reranker = (
                QwenReranker(device=container.settings.embedding_device)
                if variant == "hybrid_rerank"
                else None
            )
            backend = ExperimentalRetriever(container.query.embedder, container.store, reranker)
            reports[variant] = run_retrieval_evaluation(dataset, backend, variant, args.top_k)
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(reports, ensure_ascii=False, indent=2), encoding="utf-8")
        print(json.dumps({"report": str(args.output), "variants": list(reports)}))
