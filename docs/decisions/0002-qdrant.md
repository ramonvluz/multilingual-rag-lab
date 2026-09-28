# ADR 0002: Qdrant as derived retrieval index

Qdrant provides dense search, payload filtering, aliases, and materialized BM25 with server-side IDF. Each rebuild has a unique physical generation. It is never the source of truth. BM25 uses a language-neutral no-stemming/no-stopword baseline for PT-BR/EN/ES, with parameters recorded in IndexSpec.
