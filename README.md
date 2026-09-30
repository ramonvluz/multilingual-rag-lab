# Multilingual RAG Lab

A compact, evaluation-driven Retrieval-Augmented Generation laboratory for PT-BR, English, Spanish, and cross-lingual retrieval. It demonstrates a lightweight ports-and-adapters architecture with local Qwen embeddings, Qdrant retrieval, and optional grounded Gemini generation.

## Quick start

```bash
cp .env.example .env
uv sync --locked --all-groups
# On native Linux, prepare ownership of the runtime mount once (no recursive chown):
# docker compose build app
# docker compose run --rm --no-deps --user 0 app chown 10001:10001 /app/runtime
docker compose up -d
docker compose exec app rag-lab reindex
docker compose restart app
docker compose exec app rag-lab ingest-corpus /app/data/corpus/v1.0.0
```

Use `POST /documents` to upload PDF, DOCX, HTML, Markdown, CSV, or XLSX, and `POST /query` with `{"question":"..."}`. `GET /health/live` only checks process life; readiness also requires Qdrant.

## Design

Original source files in `runtime/documents` are the source of truth. Qdrant is a reconstructable derived index, with unique physical generations named `rag_<IndexSpec fingerprint>_<uuid>`. The default operational pipeline is dense retrieval. Hybrid BM25/RRF and reranking are experimental evaluation variants, not public API choices.

`rag-lab reindex` is explicit: under a local mutation lock it builds a new empty candidate collection from persisted sources, validates every point, moves the active Qdrant alias, then atomically writes its manifest. A manifest write failure rolls back the alias, including the first-index case. Failed candidates are cleaned only when safely inactive; cleanup/rollback errors are explicit. Previous valid collections are retained for rollback. Startup never creates or reindexes an index. See architecture notes for the process-crash recovery boundary.

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

## Golden V1 retrieval evaluation (no official results published)

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

To also validate Qdrant without running retrieval or loading models, use the same
command with `--preflight-only` instead (inside Compose, mount `./evaluation:/app/evaluation`
as shown below). This prints only integrity counts and the physical snapshot name.

For a **future, explicitly authorized benchmark**, use the current app source and
the existing Compose network/cache/runtime, after the explicit migration to the corrected BM25 v2 IndexSpec:

```bash
docker compose build app
docker compose run --rm -v ./evaluation:/app/evaluation app rag-lab evaluate /app/evaluation/datasets/golden_v1.jsonl --corpus /app/data/corpus/v1.0.0 --candidate-pool 30 --top-k 10 --output /app/evaluation/results/retrieval-v1-run-001.json
```

This runs A (dense), B (dense + sparse BM25 + RRF), C (B + Qwen reranker), exclusively
in the evaluation layer by default. To run only A/B, append `--variants dense hybrid`
to the evaluate command. `hybrid_rerank` is optional and can be computationally expensive
on CPU-only systems; selecting only A/B does not instantiate the reranker.
Progress such as `[dense] 1/44` is printed to stderr for completed answerable queries,
excluding warm-up and unanswerable queries, outside the retrieval latency timer.
Each completed variant is atomically saved to the same JSON report. If a later variant
is interrupted, completed variants remain available; the unfinished variant is not saved.
This is not automatic resume: a new invocation still requires an unused output path.

Each dense/sparse branch supplies up to 30 chunks by default
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

Preflight checks schema (dense 1024/cosine, BM25 IDF), every official operational SHA,
unknown documents, chunk identity/sequence, materialized vectors and total count.
All A/B/C searches then use that exact physical collection, not the mutable alias.
Official evaluation holds the local runtime mutation lock for the entire preflight and A/B/C run, so ingest, delete and reindex using the same runtime are rejected while it is running. This does not prevent out-of-band writes made directly to Qdrant or through another coordination mechanism. Candidate JSON uses
`score_type` and `ranking_score`: dense / RRF / final reranker respectively.

The lexical baseline is FastEmbed `Qdrant/bm25`, document `embed()` and query
`query_embed()`, with Qdrant `Modifier.IDF`. Stemming **and stopwords are disabled**
for PT-BR/EN/ES; k=1.2, b=0.75, avg_len=256 and token_max_length=40 are explicit.
Embedding queries retain the approved `encode()` baseline without a query prompt.
Qwen embedding/tokenizer and reranker revisions are pinned and reported. Warm-up
loads the entire selected path; this small case study does not eliminate OS/cache/
thermal noise or claim statistical significance from a single run.

## Configuration and recovery

Compose explicitly forwards the documented model, chunk, upload and log settings;
its Qdrant URL stays `http://qdrant:6333`. `.env` is optional and never versioned.
For local Python commands, configure a reachable Qdrant URL: Compose does not publish
6333. `GEMINI_API_KEY` may be forwarded but is not required. **Gemini live remains
pending citation/abstention contract corrections; do not enable generation yet.**

The image runs as UID 10001. Its HF and FastEmbed cache directories are pre-created
with that ownership; FastEmbed persists under the same cache volume. Bind-mounted
runtime directories on native Linux need writable ownership (see quick start).
Qdrant has a real readiness healthcheck; app startup waits for it. App readiness
checks manifest/configuration/alias/schema without loading models. Before the first
explicit empty reindex, app readiness is intentionally 503; restart after that step.

Ingest retains sources on failure so retry can repair absent/partial indexing.
Completed receipts are checked against exact indexed chunk IDs. Delete is retry-safe
when vectors were removed but filesystem deletion failed. Batch summaries include
all failures and return a nonzero exit code on partial failure. Mutations on the same
runtime are serialized locally; a concurrent command fails clearly. Local lock files
are persistent coordination files, not stale-lock markers to delete manually.

Corpus files are marked `-text` in `.gitattributes`, preserving approved bytes on all
platforms. A regression test verifies the aggregate corpus SHA-256. Golden bytes
remain separately protected. No section-level changes are part of V1.

## Development

`make setup/lint/typecheck/test` runs locked setup and local quality checks. `make test`
runs the whole lightweight suite; `make integration` uses Qdrant local mode unless
`QDRANT_TEST_URL` points to a disposable test server. CI provides Qdrant Server 1.19.1,
runs the full suite and Docker build, but does not download Qwen/Docling models.
`RUN_BM25_REAL=1` opts into the small real FastEmbed test. `make smoke` checks lazy
imports, not container end-to-end behavior. `make build/up/down` manages Compose
without deleting volumes. Ingest/reindex targets run inside Compose; `FILE` is a
container path. `validate-corpus` is local and read-only. Make requires GNU Make;
on Windows use the equivalent `uv`/`docker compose` commands directly.
`make benchmark` is guarded by `CONFIRM_BENCHMARK=yes`; `OUTPUT` is optional and
defaults to the CLI output path when omitted. Use it only after separate benchmark authorization.

See [architecture](docs/architecture.md) and [ADRs](docs/decisions/).
