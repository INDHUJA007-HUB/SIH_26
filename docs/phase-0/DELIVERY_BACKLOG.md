# Prioritized implementation backlog

| Epic | Priority | Dependencies | Phase | Deliverable / exit |
| --- | --- | --- | --- | --- |
| EP-00 Scope, sources, claims, acceptance and architecture | P0 | Research | 0 | Traceability, issues, ADRs and test baseline |
| EP-01 Native/Compose platform, CI and telemetry | P0 | EP-00 | 1 | Authenticated fixture, migration/seed, worker and dashboard smoke |
| EP-02 Roles, assignments and tenant isolation | P0 | EP-01 | 2 | Denied cross-owner/property/action tests |
| EP-03 Immutable applications and audit/outbox | P0 | EP-02 | 3 | Submission race/replay history passes |
| EP-04 Safe intake/delivery/access events | P0 | EP-03 | 4 | Unsafe uploads isolated; version-specific reads |
| EP-05 Durable pipeline/fairness | P0 | EP-03/04 | 5 | Kill/retry/deadline tests |
| EP-06 Extraction/provenance/corrections | P0 | EP-04/05 | 6 | Regions resolve; unknowns/corrections versioned |
| EP-07 Rule DSL/resolution/evaluator | P0 | EP-06 and policy subset | 7 | Golden results and frozen replay |
| EP-08 Records/source adapters/manual paths | P0 | EP-05/06; onboarding | 8 | Six statuses; labels; authorized source evidence |
| EP-09 Reports/review/scoped response | P0 | EP-07/08 | 9 | Two audiences; blocked unrelated edit; finding diff |
| EP-10 Tasks/timers/alerts/audit views | P0 | EP-03/05/09 | 10 | One semantic alert; correct owner/timeline |
| EP-11 Media/visible discrepancy | P1, mandatory addition with permitted CV fallback | EP-04/06 | 11 | Real bounded analysis/manual fallback; advisory output |
| EP-12 Change governance/replay/remedies | P1 | EP-07/09/10 | 12 | Distinct approver; unchanged history; limited scenarios |
| EP-13 Qualification and measured evaluation | P0 for pilot | All declared supported epics | 13 | Security, eight metrics, load/restore evidence |
| EP-14 Production deployment/controlled pilot | P0 for pilot | EP-13 and external approvals | 14 | Named owners; approved scope and restore results |
| EP-15 Operation/drift/scale | Ongoing | EP-14 | 15 | Reviewed changes, access/retention and capacity |

Milestones: weeks 1–2 baseline/foundation; 3–6 identity/application/intake/workflows; 7–13 extraction/rules/sources/review; 10–16 media/alerts/governance; 17–20 qualification; 21–24 controlled pilot. This is an estimate for the six-person engineering team in the implementation plan, not a delivered schedule or guaranteed external onboarding date.
