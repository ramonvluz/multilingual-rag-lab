from __future__ import annotations

import json
from collections import Counter
from pathlib import Path
from typing import Any

GOLDEN_V1_DISTRIBUTION = {
    "semantic": 8,
    "exact": 6,
    "mixed": 6,
    "cross_lingual": 8,
    "multi_context": 6,
    "versioning": 6,
    "ambiguous": 4,
    "unanswerable": 4,
}
OFFICIAL_DOCUMENT_IDS = {f"DOC-{number:03d}" for number in range(1, 25)}


def validate_dataset(rows: list[dict[str, Any]], *, official_v1: bool = False) -> None:
    required = {
        "query_id",
        "query",
        "query_language",
        "primary_type",
        "tags",
        "answerability",
        "relevant_documents",
        "reference_answer",
        "notes",
    }
    ids: set[str] = set()
    if not rows:
        raise ValueError("Dataset is empty")
    for number, row in enumerate(rows, 1):
        if not isinstance(row, dict) or set(row) != required:
            raise ValueError(f"Dataset row {number}: inconsistent Golden V1 schema")
        for field in required - {"tags", "relevant_documents"}:
            if not isinstance(row[field], str):
                raise ValueError(f"Dataset row {number}: {field} must be a string")
        if not row["query_id"] or row["query_id"] in ids or not row["query"].strip():
            raise ValueError(f"Dataset row {number}: duplicate/empty query ID or query")
        ids.add(row["query_id"])
        for field in ("tags", "relevant_documents"):
            values = row[field]
            if not isinstance(values, list) or not all(isinstance(v, str) for v in values):
                raise ValueError(f"Dataset row {number}: {field} must be a string list")
            if len(values) != len(set(values)):
                raise ValueError(f"Dataset row {number}: duplicate {field}")
        if row["primary_type"] not in GOLDEN_V1_DISTRIBUTION:
            raise ValueError(f"Dataset row {number}: unknown primary_type")
        if row["query_language"] not in {"pt-BR", "en", "es"}:
            raise ValueError(f"Dataset row {number}: unknown query_language")
        if row["answerability"] not in {"answerable", "unanswerable"}:
            raise ValueError(f"Dataset row {number}: invalid answerability")
        positive = row["answerability"] == "answerable"
        if positive != bool(row["relevant_documents"]) or positive == (
            row["primary_type"] == "unanswerable"
        ):
            raise ValueError(f"Dataset row {number}: inconsistent answerability/ground truth")
        unknown = set(row["relevant_documents"]) - OFFICIAL_DOCUMENT_IDS
        if unknown:
            raise ValueError(f"Dataset row {number}: invalid DOC IDs {sorted(unknown)}")
    if official_v1:
        if len(rows) != 48 or ids != {f"Q-{n:03d}" for n in range(1, 49)}:
            raise ValueError("Golden V1 requires exactly Q-001 through Q-048")
        if Counter(row["primary_type"] for row in rows) != GOLDEN_V1_DISTRIBUTION:
            raise ValueError("Golden V1 primary_type distribution differs from specification")
        gaps = {row["query_id"] for row in rows if row["answerability"] == "unanswerable"}
        if gaps != {f"Q-{n:03d}" for n in range(45, 49)}:
            raise ValueError(
                "Golden V1 requires 44 answerable and Q-045 through Q-048 unanswerable"
            )


def load_dataset(path: Path) -> list[dict[str, Any]]:
    rows = []
    for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if line.strip():
            try:
                rows.append(json.loads(line))
            except json.JSONDecodeError as error:
                raise ValueError(f"Invalid JSON in dataset line {number}") from error
    validate_dataset(rows, official_v1=True)
    return rows
