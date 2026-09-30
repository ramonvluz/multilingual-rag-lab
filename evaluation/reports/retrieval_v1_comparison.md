# Retrieval V1 — run-001 × run-002 release evidence

Dense reproduced its document-level rankings and quality exactly in these two runs.
Hybrid retained aggregate Recall, with 14 changed document rankings and one query
with changed position-sensitive metrics. Run-001 remains the V1 reference benchmark;
run-002 is a post-freeze reproducibility check, not a replacement baseline.

## Sources and comparability

Sources: unchanged [run-001 JSON](../results/retrieval-v1-run-001.json) and
[run-002 JSON](../results/retrieval-v1-run-002.json). This report compares stored
results by `query_id`; it does not rerun retrieval or alter scoring.

| Run | Variant | JSON timestamp (UTC) | query_count | positive_query_count | unanswerable_count |
|---|---|---|---:|---:|---:|
| 001 | Dense (A) | 2026-09-29T19:52:58.623294+00:00 | 48 | 44 | 4 |
| 001 | Hybrid (B) | 2026-09-29T19:53:56.917340+00:00 | 48 | 44 | 4 |
| 002 | Dense (A) | 2026-09-30T21:03:07.412961+00:00 | 48 | 44 | 4 |
| 002 | Hybrid (B) | 2026-09-30T21:03:46.635765+00:00 | 48 | 44 | 4 |

Both JSONs contain only A (Dense) and B (Dense + BM25 + RRF). Query inputs and
ground truth match for all 48 IDs. Positive metrics are binary document-level
macro-averages over 44 answerable queries, with first-occurrence document
deduplication. The four unanswerable records have null metrics and empty rankings;
they are not retrieved/scored and do not establish abstention quality.

Per variant, the only metadata differences are timestamps and the application
package version (`0.1.0` → `1.0.0`). The following are identical: corpus manifest
and Golden hashes, all 24 operational document mappings and per-document point
counts, 189 indexed points, physical collection, alias `rag_active`, IndexSpec and
fingerprint `2e80d0b46cbcce81`, model revisions, BM25 configuration, candidate pool
30, maximum document k 10, fusion/scoring and warm-up/latency policies.
Recorded Python (3.12.14), Linux/WSL2 platform, CPU device and dependency versions
also match. The project owner identifies the same reference machine (Intel
i5-8365U, 32 GB RAM) and freeze commit `e3d56f5`; the JSONs do not record hardware
identity or a Git SHA, so those details are supplied context, not inferred metadata.

## Aggregate quality

Values below are taken from `aggregate.metrics`, rounded to six decimals.

| Metric | Dense 001 | Dense 002 | Hybrid 001 | Hybrid 002 |
|---|---:|---:|---:|---:|
| Recall@1 | 0.640152 | 0.640152 | 0.606061 | 0.606061 |
| Recall@3 | 0.856061 | 0.856061 | 0.750000 | 0.750000 |
| Recall@5 | 0.901515 | 0.901515 | 0.852273 | 0.852273 |
| MRR@10 | 0.818615 | 0.818615 | 0.757828 | 0.756692 |
| nDCG@5 | 0.819711 | 0.819711 | 0.762214 | 0.761218 |
| nDCG@10 | 0.839826 | 0.839826 | 0.796361 | 0.795365 |

Dense aggregate quality is exactly equal before rounding. Hybrid Recall@1/@3/@5
is also exactly equal; its MRR@10 difference is approximately -0.001136 and its
nDCG@5/@10 differences are approximately -0.000996 (run-002 minus run-001).

## Per-query stability

- **Dense:** all 44 answerable `retrieved_documents` lists match exactly, including
  order, and all per-query metric dictionaries match. The four unanswerable
  empty/null results also match.
- **Hybrid:** 30/44 answerable document rankings match exactly. The 14 changed
  lists are Q-003, Q-007, Q-009, Q-012, Q-015, Q-021, Q-023, Q-024, Q-026, Q-032,
  Q-034, Q-037, Q-038 and Q-041. Twelve are order-only differences; Q-021 and
  Q-034 also differ in document membership within the recorded top-10.
  Thirteen of these 14 queries retain all per-query metrics. Only Q-024 changes
  metrics; therefore 43/44 answerable metric dictionaries match exactly.

For Hybrid Q-024, the sole relevant document, `DOC-013`, moves from position 4 to
position 5. These are the unrounded stored values:

| Q-024 metric | run-001 | run-002 |
|---|---:|---:|
| MRR@10 | 0.25 | 0.2 |
| nDCG@10 | 0.43067655807339306 | 0.38685280723454163 |
| nDCG@5 | 0.43067655807339306 | 0.38685280723454163 |
| Recall@5 | 1.0 | 1.0 |

Recall@1 and Recall@3 remain 0.0 for this query. Its metric differences, divided
by the 44 positive queries, account for the Hybrid aggregate quality differences.
The artifacts establish the observed variation, not its cause; they do not justify
labeling it a bug, regression or improvement.

## Observed warm-state latency

Stored `aggregate.latency_ms`, rounded to one decimal; 44 measured queries per
variant/run. The matching policy excludes model initialization, warm-up, mapping
setup, metrics and serialization, and includes retrieval through document deduplication.

| Variant | Mean 001 (ms) | Mean 002 (ms) | p50 001 (ms) | p50 002 (ms) | p95 001 (ms) | p95 002 (ms) |
|---|---:|---:|---:|---:|---:|---:|
| Dense | 1298.3 | 845.4 | 1301.7 | 843.2 | 1756.7 | 1314.7 |
| Hybrid | 1294.9 | 875.7 | 1290.8 | 838.6 | 1809.7 | 1144.6 |

Run-002 has lower observed latency, but two executions on the same reference
machine are not a statistical performance study. Cache, warm state, OS activity
and thermal conditions can affect timing; no cause or proven speedup is claimed.

## Release conclusion

These executions demonstrate exact Dense document-level ranking/quality reproduction
and near-stable Hybrid quality, with preserved aggregate Recall and small changes
in ordering and position-sensitive metrics. They do not prove absolute determinism
or answer-bearing chunk coverage, and do not change the operational generation path.

C remains experimental and was considered operationally infeasible on the reference
CPU-only machine after the earlier interrupted attempt. No C execution was needed
for release closure; neither JSON contains a C result. See the
[V1 summary](retrieval_v1_summary.md) for the reference benchmark and limitations.
