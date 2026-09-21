# Architecture

Inbound FastAPI and CLI adapters invoke application use cases. The application layer only depends on ports for parsing, chunking, embeddings, source persistence, vector retrieval, reranking, and generation. The composition root connects those ports to Docling, Qwen, Qdrant, filesystem, and Gemini adapters.

Ingestion validates a filename and payload, creates a SHA-256 content identity, saves the original under an internal document ID path, parses, chunks, embeds, and indexes it. The same bytes are idempotent.

Query embeds the original multilingual question without translation, retrieves dense candidates, builds chunk-labelled context, and optionally invokes Gemini. Citations are accepted only when they match retrieved chunk IDs.

Each `IndexSpec` captures model, dimension, distance, chunking strategy/version, and sparse strategy. Its fingerprint names the derived Qdrant collection. Explicit reindexing creates a new collection and promotes it only after complete indexing; the active index remains untouched on failure.

Compose has only `app` and `qdrant`. Documents, index manifests, Qdrant storage, and the Hugging Face cache are persisted outside the image; the app runs non-root.
