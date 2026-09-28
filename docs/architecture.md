# Architecture

Inbound FastAPI and CLI adapters invoke application use cases. The application layer only depends on ports for parsing, chunking, embeddings, source persistence, vector retrieval, reranking, and generation. The composition root connects those ports to Docling, Qwen, Qdrant, filesystem, and Gemini adapters.

Ingestion validates a filename and payload, creates a SHA-256 content identity, saves the original under an internal document ID path, parses, chunks, embeds, and indexes it. The same bytes are idempotent.

Query embeds the original multilingual question without translation, retrieves dense candidates, builds chunk-labelled context, and optionally invokes Gemini. Citations are accepted only when they match retrieved chunk IDs.

Each `IndexSpec` captures embedding/tokenizer revisions, dimension, distance, chunking strategy/version/size and the materialized sparse configuration. `qdrant-bm25-idf-v2` uses FastEmbed document `embed`, query `query_embed`, Qdrant IDF, and no language-specific stemming/stopwords. Defaults k=1.2, b=0.75, avg_len=256, token_max_length=40 are explicit. English is the library's inert language parameter with stemming disabled, not an English lexical pipeline.

Physical generations are `rag_<fingerprint>_<uuid>`. A local OS-backed runtime mutation lock serializes ingest, delete and reindex. Reindex always builds a new empty collection, validates all chunk identities, source coverage, vectors and counts, then promotes `rag_active` and atomically replaces the manifest using a unique temporary file. If promotion/manifest persistence raises, the previous alias (or absence of alias) is restored. Failed candidates are removed only after confirming they are not active; recovery failures name the candidate and require explicit reconciliation. Previous valid generations are retained, not automatically deleted.

Alias and filesystem are not a distributed transaction: a process/machine crash between promotion and manifest replacement may leave a mismatch. Startup/readiness fail closed in that state; inspect both states and explicitly rerun reindex to rebuild from validated sources. OS locks release on process death. Never manually remove a lockfile while another process holds it.

Ingestion retains original sources after failure. A receipt records exact chunk identities and configuration fingerprint; idempotence checks the active index, and missing/partial indexing is repaired. Legacy sources without receipts are parsed once to verify expected identities, without embedding/upsert if already complete. Uncertain writes receive best-effort document-scoped compensation; a failed compensation is surfaced and retry remains possible. Delete removes vectors idempotently before removing sources and permits retry after a partial failure. Repository reads reject corrupt metadata, missing sources, hash mismatches and unsafe identifiers.

Evaluation validates corpus/runtime mapping plus full Qdrant contents and binds all variants to the validated physical generation. It holds the local runtime mutation lock for the entire preflight and A/B/C run, so ingest, delete and reindex using the same runtime are rejected while it is running. The physical collection name prevents alias drift, but out-of-band writes made directly to Qdrant or through another coordination mechanism remain outside that local guarantee. Scores are labelled dense, RRF or reranker. Golden V1 remains document-level.

Compose has only `app` and `qdrant`. Documents, index manifests, Qdrant storage, and the Hugging Face cache are persisted outside the image; the app runs non-root.
