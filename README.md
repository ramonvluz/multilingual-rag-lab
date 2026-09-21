# Multilingual RAG Lab

A compact, evaluation-driven Retrieval-Augmented Generation laboratory for PT-BR, English, Spanish, and cross-lingual retrieval. It demonstrates a lightweight ports-and-adapters architecture with local Qwen embeddings, Qdrant retrieval, and optional grounded Gemini generation.

## Quick start

```bash
cp .env.example .env
uv sync --all-groups
docker compose up -d qdrant
uv run rag-lab reindex
uv run uvicorn multilingual_rag_lab.adapters.inbound.api.app:app --reload
```

Use `POST /documents` to upload PDF, DOCX, HTML, Markdown, CSV, or XLSX, and `POST /query` with `{"question":"..."}`. `GET /health/live` only checks process life; readiness also requires Qdrant.

## Design

Original source files in `runtime/documents` are the source of truth. Qdrant is a reconstructable derived index named from a deterministic `IndexSpec` fingerprint. The default operational pipeline is dense retrieval. Hybrid BM25/RRF and reranking are experimental evaluation variants, not public API choices.

`rag-lab reindex` is explicit: it builds and validates a candidate collection from persisted sources, atomically moves the active Qdrant alias, then records its manifest. Startup never creates or reindexes an index.

The API runs without a Gemini key; generation then abstains while still returning retrieval evidence. Never expose this local demonstration service publicly without authentication, authorization, upload hardening, and operational controls.

## Development

`make lint`, `make typecheck`, `make test`, `make integration`, `make build`, `make up`, `make down`, and `make smoke` use the same workflow as CI. A real Gemini request is intentionally excluded from standard tests.

See [architecture](docs/architecture.md) and [ADRs](docs/decisions/).
