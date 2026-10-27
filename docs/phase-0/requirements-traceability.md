# Requirements traceability

Status refers to the present delivery: F = foundation implemented; B = specified baseline, implementation in the listed later phase; G = external approval gate. Acceptance scenarios are in pilot-scope-and-acceptance.md. Every requirement has a functional owner; names are pending organization assignment.

| ID | Requirement | Owner | Phase | Acceptance evidence | Status |
| --- | --- | --- | --- | --- | --- |
| REQ-001 | Isolated institutions and officer assignments | Backend/security | 2 | Cross-owner object/property denial | B |
| REQ-002 | Frozen application revision and evidence manifest | Backend | 3 | Original hash unchanged after response | B |
| REQ-003 | Quarantine, limits and safe file acceptance | Backend/platform | 4 | Unsafe/type/checksum/race fixtures | B |
| REQ-004 | Page regions, transforms and raw/normalized fields | ML/backend | 6 | Field opens exact source region | B |
| REQ-005 | Versioned human corrections | Backend | 6 | Prior fact set remains replayable | B |
| REQ-006 | Effective/observed historical records | Integration | 8 | Stale and conflicting history identified | B |
| REQ-007 | Independent completeness/source/forensic dimensions | Policy/backend | 7–10 | Forensic changes leave source state unchanged | B |
| REQ-008 | Six source statuses and explicit method | Integration | 8 | Six-result mapping including outage | B |
| REQ-009 | Pure deterministic sourced rule evaluation | Policy/backend | 7 | Golden results and replay, unknown abstention | B |
| REQ-010 | Source/interpretation/test/publication gates | Policy owner | 7,12 | All gates bound to candidate hash | G |
| REQ-011 | Distinct author/approver | Policy/backend | 2,12 | Same person changing role cannot self-approve | B |
| REQ-012 | Frozen-run amendment impact and replay | Backend | 12 | Old run unchanged after publication | B |
| REQ-013 | Officer/applicant JSON/PDF reports | Product/backend | 9 | Audience-specific disclosure and lineage | B |
| REQ-014 | Scoped response windows and reassessment | Process/backend | 9 | Authorized response accepted; intake edit denied | G |
| REQ-015 | Owned pending actions and audit screen data | Backend | 9,10 | Actual stored timeline/task agreement | B |
| REQ-016 | Document view/download/range access history | Security/backend | 4,10 | Attempt/bytes/abort events; denied access logged | B |
| REQ-017 | Trigger/timer/recipient alert deduplication | Backend | 10 | Replayed unchanged condition creates one alert | B |
| REQ-018 | Advisory video metadata/duration/frame/GPS checks | ML | 11 | Role-specific duration, neutral missing GPS | B |
| REQ-019 | Visible room discrepancy check | ML/product | 11 | Held-out count/overlay or explicit manual fallback | B |
| REQ-020 | Idempotent durable jobs and bounded queues | Platform/backend | 5 | Kill/retry/outage tests | B |
| REQ-021 | Typed configuration, health/build and fixture API | Backend | 1 | Unit and real HTTP smoke | F |
| REQ-022 | Framework-free business module contracts | Technical lead | 1 | AST import-boundary gate | F |
| REQ-023 | Repeatable local environment and seeds | Platform | 1 | Bootstrap repeatability; Compose/full-stack smoke | F; Docker execution gate |
| REQ-024 | CI lint/types/tests/migrations/security/SBOM | Platform/QA | 1 | Quality/security workflows and local equivalents | F; remote CI gate |
| REQ-025 | Content-free logs/traces and local dashboards | Platform/security | 1 | Redaction/propagation tests; dashboard config | F; dashboard runtime gate |
| REQ-026 | Retention classes, holds and safe deletion | Data/security | 0,14–15 | Approved policy then purge/restore tests | G |
| REQ-027 | Checkpointed audit integrity | Security/backend | 3,10 | Concurrent chain, tamper and archive checks | B |
| REQ-028 | Approved provider access/coverage and simulation labels | Integration owner | 8 | No mock success in live metrics | G |
| REQ-029 | Eight metrics with honest denominators | QA/policy | 13 | Frozen test manifest and measured report | B |
| REQ-030 | Reproducible cloud deployment and recovery | Platform | 14 | Signed release, restore/reconciliation drill | B |
| REQ-031 | Transparent limited remedy scenarios | Policy/backend | 12 | Same-engine re-evaluation; no approval promise | B |
| REQ-032 | Safe endpoint/network integration | Security/integration | 4,8 | SSRF/redirect/replay/response limits | B |
| REQ-033 | Licensing/model and language scope | ML/legal | 0,6,11 | Version/weight inventory and validated language strata | G |
| REQ-034 | No machine adverse action | Policy/technical lead | All | Seed DB constraints and capability contract | F for foundation; ongoing |

Seven additions map to REQ-018, 017, 013/014, 016, 015, 019 and 007/008 respectively. Broader production features are intentionally not presented as Phase 1 implementations.
