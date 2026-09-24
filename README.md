# Multilingual RAG Lab

A compact, evaluation-driven Retrieval-Augmented Generation laboratory for PT-BR, English, Spanish, and cross-lingual retrieval. It demonstrates a lightweight ports-and-adapters architecture with local Qwen embeddings, Qdrant retrieval, and optional grounded Gemini generation.

## Quick start

```bash
cp .env.example .env
uv sync --all-groups
docker compose up -d
docker compose exec app rag-lab reindex
docker compose restart app
docker compose exec app rag-lab ingest-corpus /app/data/corpus/v1.0.0
```

Use `POST /documents` to upload PDF, DOCX, HTML, Markdown, CSV, or XLSX, and `POST /query` with `{"question":"..."}`. `GET /health/live` only checks process life; readiness also requires Qdrant.

## Design

Original source files in `runtime/documents` are the source of truth. Qdrant is a reconstructable derived index named from a deterministic `IndexSpec` fingerprint. The default operational pipeline is dense retrieval. Hybrid BM25/RRF and reranking are experimental evaluation variants, not public API choices.

`rag-lab reindex` is explicit: it builds and validates a candidate collection from persisted sources, atomically moves the active Qdrant alias, then records its manifest. Startup never creates or reindexes an index.

## Official corpus

The versioned official dataset lives in `data/corpus/v1.0.0`; its 24 original files and
manifest are not runtime state. `runtime/documents` contains operational source copies
created by ingestion, while Qdrant is a derived, rebuildable index.

For a new clone, start the Compose stack, explicitly create the initial empty active
index with `docker compose exec app rag-lab reindex`, restart the app so it loads that
manifest, then run `docker compose exec app rag-lab ingest-corpus /app/data/corpus/v1.0.0`.
The command validates `manifest.json`, declared files, IDs, extensions, extras, and the
expected document count before invoking the same `IngestDocument` used by the HTTP API.
Validate without ingesting with `rag-lab validate-corpus data/corpus/v1.0.0` (or, in
Compose, `/app/data/corpus/v1.0.0`).
Run the explicit reindex command again only when rebuilding an index.

The API runs without a Gemini key; generation then abstains while still returning retrieval evidence. Never expose this local demonstration service publicly without authentication, authorization, upload hardening, and operational controls.

## Golden V1 retrieval evaluation (benchmark not yet run)

The approved, unchanged 48-query dataset is `evaluation/datasets/golden_v1.jsonl`.
Its supplied audit and summary are in `evaluation/reports/`. Ground truth is binary
**document-level**, using stable DOC-001–DOC-024 identifiers; section-level is future work.
The existing `evaluate` command resolves every manifest filename to exactly one
`FileSystemDocumentRepository` document and verifies the official and operational
source SHA-256. Missing, ambiguous or mismatched sources stop evaluation.

Validate dataset and all 24 mappings without querying Qdrant or loading models:

```bash
uv run rag-lab evaluate evaluation/datasets/golden_v1.jsonl --validate-only
```

For a **future, explicitly authorized benchmark**, use the current app source and
the existing Compose network/cache/runtime (no reindex needed):

```bash
docker compose build app
docker compose run --rm -v ./evaluation:/app/evaluation app rag-lab evaluate /app/evaluation/datasets/golden_v1.jsonl --corpus /app/data/corpus/v1.0.0 --candidate-pool 30 --top-k 10 --output /app/evaluation/results/retrieval-v1-run-001.json
```

This runs A (dense), B (dense + sparse BM25 + RRF), C (B + Qwen reranker), exclusively
in the evaluation layer. Each dense/sparse branch supplies up to 30 chunks by default
(3 × the maximum document k). B uses the complete RRF union (constant 60); C reranks
that complete union. All variants then keep the first occurrence of each document
before taking the document top-k. An exhausted candidate pool is reported; it is not
silently expanded or padded. Chunk IDs, scores and resulting stable document ranks
remain available in the JSON for inspection.

The 44 answerable queries produce Recall@1/@3/@5, MRR@10, nDCG@5/@10, macro-averaged
per query, with all relevant documents retained in multi-document ground truth.
Reports include aggregate, `by_primary_type`, `by_query_language`, and full per-query
annotations. The four unanswerable queries are preserved separately by their
`evaluation_group=unanswerable_abstention`, with null metrics/latency, and are not
retrieved or included in positive aggregates. No abstention metric is defined yet.

Every variant runs one unmeasured full-path warm-up using the fixed synthetic query
`OrbeFlow retrieval warm-up` before timing any dataset query. Reported latency covers
warm-state retrieval through document deduplication, excluding model initialization,
source validation, scoring and serialization. Mean/p50/p95 cover the 44 answerable
queries; percentiles use linear interpolation at `(n-1)*p`. The report records the
policy, UTC timestamp, dataset/corpus hashes and versions, package versions, device,
model names, IndexSpec/fingerprint, collection/alias, document mapping and pool sizes.
Use a new output filename for every run; existing reports are not overwritten.
`evaluation/results/` is versionable and currently contains no benchmark results.

## Development

`make lint`, `make typecheck`, `make test`, `make integration`, `make build`, `make up`, `make down`, and `make smoke` use the same workflow as CI. A real Gemini request is intentionally excluded from standard tests.

See [architecture](docs/architecture.md) and [ADRs](docs/decisions/).
