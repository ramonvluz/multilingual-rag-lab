from __future__ import annotations

import argparse
import json
from pathlib import Path

from multilingual_rag_lab.bootstrap.composition import build_container


def main() -> None:
    parser = argparse.ArgumentParser(prog="rag-lab")
    commands = parser.add_subparsers(dest="command", required=True)
    ingest = commands.add_parser("ingest")
    ingest.add_argument("file", type=Path)
    commands.add_parser("reindex")
    evaluate = commands.add_parser("evaluate")
    evaluate.add_argument("dataset", type=Path)
    args = parser.parse_args()
    container = build_container()
    if args.command == "ingest":
        document, created = container.ingest.execute(args.file.name, args.file.read_bytes())
        print(json.dumps({"document_id": document.document_id, "created": created}))
    elif args.command == "reindex":
        print("Reindex requires an explicit invocation; no index is changed by startup.")
    else:
        print(json.dumps({"dataset": str(args.dataset), "status": "evaluation scaffold"}))
