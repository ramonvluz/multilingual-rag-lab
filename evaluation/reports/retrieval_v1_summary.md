# Retrieval V1 — run-001 and release reproduction protocol

Dense achieved higher aggregate document-level retrieval-quality metrics than Hybrid
in run-001 and is the V1 reference baseline. This result is specific to a small
synthetic corpus and the reference CPU environment; Hybrid performs better on the
exact-query slice. Neither outcome establishes a universally superior strategy or
measures correctness of generated answers.

## Evidence and scope

The source is the unchanged [run-001 JSON](../results/retrieval-v1-run-001.json),
completed on 2026-09-29 (UTC). Tables below read its stored `aggregate`,
`by_primary_type` and `by_query_language` fields; no retrieval was rerun to prepare
this report. Quality values are rounded to four decimals, latency to one decimal.

- Corpus: [v1.0.0](../../data/corpus/v1.0.0/manifest.json), 24 synthetic documents in
  PT-BR, English and Spanish, across PDF, DOCX, HTML, Markdown, CSV and XLSX.
- Golden: [golden_v1.jsonl](../datasets/golden_v1.jsonl), Q-001–Q-048; 44 answerable
  queries and four unanswerable queries excluded from positive retrieval metrics.
- Ground truth: binary **document-level** relevance, using stable DOC-001–DOC-024.
  The runner resolves those IDs to operational SHA-256 sources, deduplicates retrieved
  chunks to documents by first occurrence, and macro-averages metrics over queries.
- Index reported by run-001: 189 points, fingerprint `2e80d0b46cbcce81`;
  candidate pool 30 chunks per branch, maximum document k = 10.
- A: Dense. B: Dense + materialized BM25 + RRF, constant 60, full candidate union.
  Each variant runs an unmeasured full-path warm-up. Latency includes retrieval through
  document deduplication, excluding initialization, metric calculation and serialization.
- Reference hardware supplied by the project owner: Intel i5-8365U, 32 GB RAM,
  CPU-only Docker. JSON provenance records Linux/WSL2, Python 3.12.14,
  torch 2.14.0+cpu, sentence-transformers 5.7.0, transformers 5.17.0,
  FastEmbed 0.8.0 and qdrant-client 1.19.1.
- The historical application package version is `0.1.0`. The raw report does not
  record a Git SHA; none is inferred or retroactively inserted here.

## Aggregate results — 44 answerable queries

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

Mean and median latency are close in this single run; no statistical significance
or general performance advantage is claimed. Percentiles use linear interpolation
at `(n - 1) * p`. Multi-document queries retain all declared relevant documents.

## By primary type

Values are taken directly from the corresponding stored group aggregates. Counts
are answerable queries; the four unanswerable queries have null positive metrics.

| primary_type | n | A Recall@5 | B Recall@5 | A MRR@10 | B MRR@10 | A nDCG@10 | B nDCG@10 |
|---|---:|---:|---:|---:|---:|---:|---:|
| ambiguous | 4 | 1.0000 | 0.5000 | 0.8000 | 0.5833 | 0.8467 | 0.6781 |
| cross_lingual | 8 | 0.8750 | 0.7500 | 0.7917 | 0.4076 | 0.8125 | 0.5170 |
| exact | 6 | 0.6667 | 1.0000 | 0.5476 | 1.0000 | 0.6548 | 1.0000 |
| mixed | 6 | 1.0000 | 1.0000 | 0.9167 | 0.9167 | 0.9385 | 0.9385 |
| multi_context | 6 | 0.8333 | 0.7500 | 0.7833 | 0.5417 | 0.7465 | 0.6277 |
| semantic | 8 | 1.0000 | 1.0000 | 1.0000 | 1.0000 | 1.0000 | 1.0000 |
| versioning | 6 | 0.9444 | 0.8333 | 0.8333 | 0.8333 | 0.8379 | 0.7990 |

Hybrid leads on the six exact queries; Dense leads on cross-lingual and ambiguous
queries in these reported metrics. Small subgroup sizes limit generalization.

## By query language

| query_language | n | A Recall@5 | B Recall@5 | A MRR@10 | B MRR@10 | A nDCG@10 | B nDCG@10 |
|---|---:|---:|---:|---:|---:|---:|---:|
| en | 14 | 0.8929 | 0.8452 | 0.7388 | 0.7262 | 0.8125 | 0.7832 |
| es | 9 | 0.8889 | 1.0000 | 0.8889 | 0.8556 | 0.8800 | 0.8901 |
| pt-BR | 21 | 0.9127 | 0.7937 | 0.8417 | 0.7370 | 0.8408 | 0.7650 |

Language slices reflect the language of the question, not an isolated measure of
cross-lingual capability. Hybrid's Spanish slice has higher Recall@5/nDCG@10 but
lower MRR@10; aggregate conclusions must not be applied uniformly to every slice.

## Generation and limitations

Document-level scoring can reward a chunk from the right document even if it does
not contain the answer. Q-001 motivated a separate operational evidence pool:
Dense top-k + original Sparse top-k + supplemental NFKD/diacritic-stripped Sparse
top-k only when the query changes, deduplicated by chunk ID in that order. It does
not use RRF and was not substituted into the A/B benchmark.

Optional Gemini generation uses explicit retrieved-ID citations and the
`INSUFFICIENT_EVIDENCE` sentinel. The reported manual checks on Q-001, Q-029 and
Q-045 do not constitute a generation benchmark. These tables do not measure
answer-bearing chunk coverage, semantic entailment, abstention quality or section-level
relevance. The four unanswerable records are preserved but not retrieved/scored by
this harness. The corpus is synthetic; thermal/OS/cache variation is uncontrolled
in this single-run CPU case study.

C (Hybrid + Qwen3-Reranker-0.6B) was interrupted during an earlier CPU attempt due
to excessive operational cost. It remains experimental and explicitly selectable,
but there is no completed official C result and no inferred score or latency for it.

## Run-002 — PENDING RELEASE-CANDIDATE REPRODUCTION

After review and code freeze, the separately authorized official wrapper selects
only A/B and writes `/app/evaluation/results/retrieval-v1-run-002.json`:

```bash
make benchmark CONFIRM_BENCHMARK=yes
```

Follow the README's Linux output-permission instructions first. `OUTPUT` may name
another unused path; the CLI rejects an existing output. Each completed variant is
saved atomically. Do not overwrite or regenerate run-001, change the Golden, or
reindex solely for reproduction. Keep candidate pool 30, maximum document k 10,
warm-up policy, model revisions and compatible physical index fixed.

Update this report only after run-002 with the actual freeze Git SHA, configuration
and environment differences, then compare both stored reports. No run-002 values
or conclusions exist yet; this release patch does not execute it.
