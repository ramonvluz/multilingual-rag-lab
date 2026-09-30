# Multilingual RAG Lab

[English](README.md) | [Português (Brasil)](README.pt-BR.md)

This is the canonical technical README. Detailed technical documentation is maintained in English.

A compact, evaluation-driven Retrieval-Augmented Generation laboratory for PT-BR, English, Spanish, and cross-lingual retrieval. It demonstrates a lightweight ports-and-adapters architecture with local Qwen embeddings, Qdrant retrieval, and optional grounded Gemini generation.

## Quick start

Prerequisites: Docker Engine/Desktop with Compose v2 or later. Local development
also needs Python 3.12 and uv (reference version 0.9.27); GNU Make is optional.
Commands below assume the repository root. On PowerShell, `Copy-Item .env.example .env`
is equivalent to `cp`. Do not overwrite an existing private `.env`.

```bash
cp .env.example .env
# Optional for local Python development; not needed to run the containers:
uv sync --locked --all-groups
# On native Linux, prepare ownership of the runtime mount once (no recursive chown):
# docker compose build app
# docker compose run --rm --no-deps --user 0 app chown 10001:10001 /app/runtime
docker compose up -d
docker compose exec app rag-lab reindex
docker compose restart app
docker compose exec app rag-lab ingest-corpus /app/data/corpus/v1.0.0
```

The API is at `http://127.0.0.1:8000` (OpenAPI UI: `/docs`); `APP_PORT` overrides the
host port. Use `POST /documents` to upload PDF, DOCX, HTML, Markdown, CSV, or XLSX,
and `POST /query` with `{"question":"..."}`. `GET /health/live` checks process life;
`GET /health/ready` checks Qdrant plus manifest/configuration/alias/schema consistency.

## Design

Original source files in `runtime/documents` are the source of truth. Qdrant is a
reconstructable derived index, with unique physical generations named
`rag_<IndexSpec fingerprint>_<uuid>`. Operational generation and experimental
retrieval evaluation are deliberately separate paths; A/B/C are not public API choices.

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

## Grounded generation and the public query contract

`QueryKnowledge` builds its evidence pool in this exact order:

1. Dense `top_k` using the original question.
2. Sparse/BM25 `top_k` using the original question.
3. Supplemental Sparse/BM25 `top_k` using NFKD with combining marks removed,
   **only when this changes the question**. Case and punctuation are retained.
4. Deduplicate by `chunk_id`, retaining the first occurrence and its score/origin.
5. Send the entire union to the optional LLM with the original question.

There is no RRF, reranker, router or global score sort in this operational path.
`RETRIEVAL_TOP_K=5` applies separately to each branch, so the union contains at most
10 chunks without normalization or 15 with it, often fewer after deduplication.

Q-001 exposed the difference between retrieving the correct **document** and the
particular chunk containing the answer. Operational checks motivated supplemental
normalized Sparse retrieval. It augments, never replaces, original Sparse and does
not change the Golden methodology or the A/B/C evaluation algorithms.

Gemini answers only from evidence, uses exact retrieved chunk IDs as citations and
must return exactly `INSUFFICIENT_EVIDENCE`, with no citations or extra text, when
evidence cannot answer the question. The use case checks that sentinel after stripping
outer whitespace and returns the canonical answer:
`I don't have enough evidence to answer this question.`
It sets `abstained=true`, clears `cited_chunk_ids` and preserves `sources`.
Without the sentinel, only retrieved IDs actually present in the answer are accepted;
invented IDs are ignored. Zero valid IDs also causes canonical abstention. Valid
answers are returned unchanged. No evidence skips generation; no configured LLM
keeps evidence but abstains with the generation-not-configured message.

`sources` contains `document_id` (operational SHA-256), `chunk_id`, `filename`,
`score` and `retrieval_method`:

| retrieval_method | Meaning of score |
|---|---|
| `dense` | Cosine similarity |
| `sparse_original` | BM25 for the original query |
| `sparse_normalized` | BM25 for the supplemental normalized query |

These scales are **not comparable**. Sources are in context-construction order,
not a global relevance ranking. A chunk found in several branches keeps the first
branch's provenance and score. Sources may include evidence not cited by the answer.
`metadata` is currently an empty extensible object. This is citation-ID validation,
not semantic verification of every claim or a guarantee that the model obeys its prompt.

The API rejects blank/whitespace-only questions with 422 without changing valid
questions. Expected application failures use JSON `{"detail":"..."}`:
404 document missing; 400 unsupported/unsafe filename or empty upload; 413 oversized
upload; 409 mutation busy; 503 unavailable dependency or unready/incompatible index;
502 generation-provider failure; 500 corrupt document/internal ingestion or application
failure. Internal diagnostics and tracebacks are not exposed.

## Golden V1 retrieval evaluation

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

### Official run-001 and completed post-freeze reproduction

The official [run-001 JSON](evaluation/results/retrieval-v1-run-001.json) contains
A (Dense) and B (Dense + BM25 + RRF). The reference environment is CPU-only Docker
on an Intel i5-8365U with 32 GB RAM; this is not a universal performance claim.

| Metric | Dense (A) | Hybrid (B) |
|---|---:|---:|
| Mean latency (ms) | 1298.3 | 1294.9 |
| p50 latency (ms) | 1301.7 | 1290.8 |
| p95 latency (ms) | 1756.7 | 1809.7 |
| MRR@10 | 0.8186 | 0.7578 |
| nDCG@10 | 0.8398 | 0.7964 |
| nDCG@5 | 0.8197 | 0.7622 |
| Recall@1 | 0.6402 | 0.6061 |
| Recall@3 | 0.8561 | 0.7500 |
| Recall@5 | 0.9015 | 0.8523 |

Dense achieved higher aggregate retrieval-quality metrics in this document-level
run and is the V1 reference baseline, not a universally superior strategy. Hybrid
remains experimental. C (Hybrid + Qwen reranker) was interrupted during earlier
CPU validation because of excessive computational cost; there is no completed
official C result. See the [human report](evaluation/reports/retrieval_v1_summary.md)
for type/language cuts and limitations. These retrieval scores do not measure the
operational evidence union or generation correctness.

[Run-002](evaluation/results/retrieval-v1-run-002.json) was completed after code
freeze at `e3d56f5` as release reproducibility evidence. Run-001 remains the V1
reference benchmark. Dense reproduced the document-level rankings and quality
metrics of all 44 answerable queries exactly. Hybrid preserved aggregate
Recall@1/@3/@5: 14/44 document rankings changed, but 13 of those queries retained
their metrics. Only Q-024 changed quality metrics, with relevant `DOC-013` moving
from position 4 to 5; Q-021 and Q-034 also changed top-10 document membership.
See the [official comparison](evaluation/reports/retrieval_v1_comparison.md).
The cause of Hybrid variation is not established, and two runs do not prove absolute
determinism. Lower observed run-002 latency is not a proven performance improvement:
cache, warm state, OS activity and thermal conditions were not statistically controlled.
C remains experimental and was operationally infeasible on the reference CPU-only
machine; no additional C run was needed for release closure.

Do not reindex merely to repeat evaluation against the already compatible index.
For any separately authorized additional run, choose an unused output path, build
the reviewed source and use the existing
Compose network/cache/runtime. On native Linux, give container UID 10001 write
access specifically to `evaluation/results`, not to the frozen dataset or reports:

```bash
docker compose build app
docker compose run --rm --no-deps --user 0 -v ./evaluation:/app/evaluation app chown 10001:10001 /app/evaluation/results
```

For an additional authorized A/B evaluation, use a new output filename
(replace `retrieval-new-run.json` if it already exists):

```bash
make benchmark CONFIRM_BENCHMARK=yes OUTPUT=/app/evaluation/results/retrieval-new-run.json
# Equivalent without GNU Make (only after separate authorization):
docker compose run --rm -v ./evaluation:/app/evaluation app rag-lab evaluate /app/evaluation/datasets/golden_v1.jsonl --corpus /app/data/corpus/v1.0.0 --candidate-pool 30 --top-k 10 --variants dense hybrid --output /app/evaluation/results/retrieval-new-run.json
```

The CLI defaults to A/B when `--variants` is omitted, and the official Make wrapper
selects A/B explicitly. C remains experimental and
available explicitly as `--variants hybrid_rerank`, exclusively in the evaluation
layer, but is not part of the official CPU release benchmark. Selecting A/B does
not instantiate the reranker. Use `OUTPUT=/app/evaluation/results/<new-name>.json`
to override the Make wrapper's run-002 default.
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
`evaluation/results/` is versionable and contains immutable run-001 and run-002
artifacts. Never overwrite either. The comparison records the supplied freeze commit
separately; neither raw JSON contains a Git SHA, and none is retroactively inferred.

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
thermal noise or establish statistically significant performance differences from these two runs.

## Configuration and recovery

Compose explicitly forwards the documented model, chunk, upload and log settings;
its Qdrant URL stays `http://qdrant:6333`. `.env` is optional and never versioned.
For local Python commands, configure a reachable Qdrant URL: Compose does not publish
6333. `GEMINI_API_KEY` may be forwarded but is not required. The reference generation
default is `LLM_MODEL=gemini-3.5-flash-lite`, used successfully in the final manual
E2E checks (Q-001, Q-029 and abstention on Q-045); it remains overridable through
`LLM_MODEL`. Those checks are not an exhaustive generation benchmark or part of CI.

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
`make benchmark` is guarded by `CONFIRM_BENCHMARK=yes`; `OUTPUT` defaults to
`/app/evaluation/results/retrieval-v1-run-002.json`, which now exists; additional
authorized runs require an unused `OUTPUT` path. CI and Docker use uv 0.9.27 and
Python 3.12. Frozen corpus, Golden, run-001 and run-002 bytes must be preserved; each report's recorded package version
must not be updated when the application version changes.

## License

MIT, copyright 2026 Ramon Valgas Luz. See [LICENSE](LICENSE).

See [architecture](docs/architecture.md) and [ADRs](docs/decisions/).
