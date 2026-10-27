# Test and evaluation strategy

Phase 1 gates: configuration, auth issuer/audience/expiry/algorithm, server-side fixture mapping, no-secret health/errors, safe request IDs, telemetry redaction, module boundaries, repeatable bootstrap, disabled seed rules, migration compilation/drift and PostgreSQL seed checks, platform workflow/HTTP smoke, Compose configuration, secret/dependency/container scan and SBOM.

Native tests execute without Docker and mark PostgreSQL integration as skipped when no URL exists; skipped is not passed. The complete Compose smoke executes on a Docker host or CI. Full Phase 2 assignment/RLS authorization is not claimed by the fixture tests.

Later layers: pure unit/property rules; real PostgreSQL/RLS/transactions; Temporal restart/replay; provider contracts/faults; upload/SSRF/security abuse; full report/response/change flows; load/soak; restore/reconciliation; paired reviewer study.

## Benchmark specification

60 development packets; 200 frozen test packets including at least 100 benign; later 300-clean safety expansion if needed. These are target sample sizes. No corpus or measured product quality is fabricated. Group same institution, revisions, near duplicates and forged twins into one split; separate template/issuer families. Two annotators plus adjudication for critical fields/findings, with policy-approved expected outcomes.

The manifest schema is in benchmarks/manifests/schema.json. It records packet/group/split/synthetic and file hashes, provenance, language/template, ground truth and adjudication references. Personal data never enters the public repository.

| Metric | Denominator | Target, not achieved |
| --- | --- | --- |
| Extraction | Required ground-truth fields including omissions | 95% digital / 90% scanned critical fields |
| Validation | Applicable adjudicated requirements; whole packet also reported | 95% agreement; ambiguity abstention |
| Anomaly | Precision/recall/F1 plus clean false flags by supported family | 90% precision / 85% recall on supported planted families |
| Source verification | Authoritatively resolved eligible claims / all eligible required claims, including outages | Unachieved without real access; mocks excluded |
| Discrepancy | Correct localized supported discrepancies / all seeded supported discrepancies | 90% recall; all evidence pointers resolve |
| Time | End-to-end/active, median/p95, pages/hardware/cold/warm, waits separate | 120s p95 only for declared 10-page local profile |
| Alerts | Trigger commit to created/visible/delivered plus duplicates | In-app p95 60s; no duplicate semantic alert |
| Manual effort | Paired review time at comparable correctness including rework | 30% reduction hypothesis |

Publish confidence intervals, denominators, unsupported strata and coverage. Threshold tuning uses development data only. Validation agreement is not proof of legal correctness; authoritative source success is not adapter status-mapping correctness.
