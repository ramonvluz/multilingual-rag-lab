# ADR 0005: Retrieval strategy remains experimental

Golden V1 is versioned with 48 queries and document-level ground truth. Dense, hybrid and reranked variants remain experimental; the official benchmark has not been run and no winner has been selected. Evaluation freezes a validated physical Qdrant collection and excludes unanswerable queries from positive retrieval metrics.

## Status amendment — 2026-09-30

The paragraph above records the pre-benchmark decision, not the current execution
status. [Run-001](../../evaluation/results/retrieval-v1-run-001.json) now contains
official A (Dense) and B (Dense + BM25 + RRF) results. Dense achieved higher aggregate
retrieval-quality metrics in this run and is the V1 reference baseline; this is not
a universal superiority claim. Hybrid remains experimental.

C (Hybrid + Qwen reranker) remains available, but an earlier CPU attempt was interrupted
because of excessive computational cost. It has no completed official result and is
not part of the official CPU release benchmark. The release Make wrapper explicitly
selects A/B, which is also the CLI default. C remains experimental and requires
explicit selection with `--variants hybrid_rerank`.

The operational generation evidence pool separately unions Dense, original Sparse and
conditional diacritic-normalized Sparse, deduplicated in that order without RRF. Q-001
motivated this distinction: finding a relevant document does not guarantee that an
answer-bearing chunk reaches generation. This does not amend the Golden ground truth,
experimental retrieval algorithms or scoring methodology. Run-002 remains pending
release-candidate reproduction after freeze. See the [human report](../../evaluation/reports/retrieval_v1_summary.md).
