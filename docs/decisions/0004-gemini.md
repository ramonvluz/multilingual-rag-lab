# ADR 0004: Gemini generation provider

Gemini is isolated behind `LLMPort`; its key is optional so standard tests have no external generation dependency.

## Amendment — 2026-09-30

The original provider-boundary decision remains accepted. Generation is grounded in
the supplied chunk-labelled evidence and may cite only exact retrieved chunk IDs.
Insufficient evidence must produce exactly `INSUFFICIENT_EVIDENCE`, without citations
or explanation. QueryKnowledge checks this sentinel (allowing outer whitespace)
before citation validation and returns canonical abstention with sources preserved.
Zero valid retrieved citations also causes abstention; otherwise the original answer
is preserved. This is an explicit protocol, not semantic entailment validation.

The V1 reference default is `gemini-3.5-flash-lite`, used in successful final manual
E2E checks; `LLM_MODEL` can override it. API keys remain optional and private. No live
provider calls or model-specific adapter behavior are added to the standard test suite.
