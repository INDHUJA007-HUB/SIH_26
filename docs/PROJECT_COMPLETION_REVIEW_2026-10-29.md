# Project identity and phase-by-phase completion review

Review date: 29 October 2026. Scope: the current working tree, including the changes already present when this review began. This is a repository and local-verification review, not a certification of regulatory compliance, cloud deployment, or production security.

## 1. What this project is

The project is the **AICTE Evidence and Compliance Workbench**, developed for **SIH 2026 problem statement PS26261**. It is intended to help institutions submit application evidence and help assigned officers inspect that evidence, identify preliminary deficiencies, request scoped corrections, and preserve an explainable history.

The repository contains two substantial layers:

1. **Research and product specification:** an AICTE handbook/amendment analysis, source register, 22 draft rule records, competitor research, architecture decisions, policy issues, and a 16-phase backend delivery plan.
2. **Backend implementation:** Python 3.12/FastAPI APIs, PostgreSQL persistence and row-level security, object-storage adapters, a real local quarantine/scanning path, Temporal workflow definitions, deterministic evaluation, review/rectification services, alerts, rule governance, media demonstrations, retention, and operations tooling.

Its intended users are institutional applicants/editors, assigned officers, supervisors, rule authors, independent rule approvers, auditors, and operators. Machine output is preliminary decision support. The design deliberately separates completeness, source verification, document validity, forensic concern, regulatory evaluation, and human disposition.

**Current overall assessment:** a substantial backend prototype with a comparatively mature local identity/intake foundation and numerous tested domain services. It is **not yet a completely integrated, validated production product**. The later-phase completion claims overstate what several implementations and tests actually establish.

There is no first-party frontend application in the reviewed source tree. API documentation and backend endpoints exist; applicant portals, officer dashboards, evidence-region viewers, audit screens, and rule-administration screens remain product integration work. Frontend delivery is not one of the backend plan's explicit 16 phases, so it should be tracked separately rather than silently treated as completed.

## 2. How to interpret status

- **Implemented:** concrete executable behavior exists for the stated scope.
- **Partial:** useful implementation exists, but some specified outputs or integration are missing.
- **Simulated:** synthetic outputs, fixed examples, or heuristic demonstrations stand in for real processing.
- **External gate:** needs organizational approval, provider access, real data, infrastructure, or independent acceptance.
- **Unproven:** the repository or local checks do not establish the claimed outcome.
- **Ongoing:** an operating responsibility that cannot be permanently finished by adding code.

A passing unit, database, or API test establishes its particular assertions. It does not automatically establish the entire phase exit gate. This distinction is essential here: some acceptance tests construct records directly, replay tests use mock activities, and several qualification tools inspect text rather than running infrastructure.

Do not derive an overall completion percentage from file counts or passing tests. The plan has no approved weighting model, and missing processing/deployment capabilities have much greater significance than their line count.

## 3. Architecture and actual execution path

| Area | Current implementation | Important boundary |
| --- | --- | --- |
| HTTP API | FastAPI routers under `backend/src/workbench/api/` | Backend contracts exist; no shipped end-user web application found |
| Data and authorization | SQLAlchemy tables, 16 Alembic revisions, PostgreSQL security functions/RLS, runtime role separation | Local fixture identities and synthetic cases are the demonstrated scope |
| Evidence intake | Upload grants, quarantine, object versions/checksums, ClamAV, isolated parser, accepted originals/previews, authorized delivery | This is the strongest integrated processing slice |
| Durable execution | Transactional outbox, intake/scan workers, workflow definitions and activity receipts | Later extraction/evaluation/report/media workers are not registered by the shipped worker entry points |
| Extraction | Digital-text geometry, regex/document classifiers, normalization, fact sets, corrections, optional PaddleOCR adapter | OCR fallback is synthetic; scanned-PDF rasterization into OCR is incomplete |
| Evaluation | Pure evaluator, bounded DSL, rule/source registry, frozen runs/findings | Demonstration rule coverage; policy approval remains external |
| Source verification | Simulator registry, six states, history import, manual confirmation | No production-authorized provider implementation demonstrated |
| Review and correction | Dispositions, audience JSON reports, response windows, diff service | Actual replacement-evidence-to-new-run orchestration remains incomplete |
| Media | Image hashes/EXIF, duration policy, sampling timestamps, equipment/floor-space demonstrations | Video frames/contact sheets and equipment detections include synthetic behavior |
| Operations | Health summaries, containment/reconciliation commands, holds/purge logic, drift demonstration | Live operating history, real restore evidence, and safe complete storage deletion remain unfinished |
| Cloud | Terraform modules and image publishing/security workflows | Provisioning scaffolding is incomplete for an operable service; cloud rollout is not established |

The shipped outbox dispatch in `platform/outbox.py` starts `ScanEvidenceWorkflow` for upload-completion events and `IntakeReceiptWorkflow` otherwise. The actual intake worker registers those two workflows. The general `worker.py` registers only `FoundationWorkflow` and `foundation_ping`. The later workflow classes are mainly exercised by test-created workers with mocks.

Consequently, the presence of `RuleEvaluationWorkflow` or `ReportGenerationWorkflow` does not mean a normal upload/submission automatically executes real evaluation or generates a report.

## 4. Phase overview

| Phase | Purpose | Assessment |
| --- | --- | --- |
| 0 | Product, policy, architecture, delivery baseline | Documentation substantially present; named approvals and refreshed traceability remain |
| 1 | Repository, local stack, CI, observability | Substantially implemented for development; remote CI and production guarantees need separate evidence |
| 2 | Identity, authorization, tenant isolation | Strong local implementation; production identity/emergency-access acceptance remains |
| 3 | Application revisions, evidence manifests, audit/outbox | Strong implemented local foundation; downstream event orchestration remains |
| 4 | Safe evidence upload, inspection, delivery | Strongest integrated slice; production storage/lifecycle qualification remains |
| 5 | Durable workflows and operational control | Partial; reliability primitives exist, later workflow activities/worker wiring incomplete |
| 6 | Extraction, provenance, normalized/versioned facts | Partial; digital/synthetic paths exist, production OCR and exact provenance need work |
| 7 | Deterministic rule evaluation | Substantial demonstration implementation; broad validated rules and production policy gate remain |
| 8 | Historical records and source authentication | Simulator/manual/history scope implemented; live connector and genuine signature validation missing |
| 9 | Officer review, reports, rectification | Partial; JSON/report/window/diff services exist, PDF and authentic reassessment pipeline missing |
| 10 | Alerts, timers, notifications, audit views | Partial; persistence and commands exist, automatic dispatch/timer/archive behavior incomplete |
| 11 | Video/image evidence and visible discrepancy | Partial/simulated; real image utilities exist, actual video/CV processing incomplete |
| 12 | Rule publication, impact, replay, remedies | Partial; governance exists, simulation/replay/remedies are narrower than the plan |
| 13 | Security, benchmarks, load, recovery qualification | Incomplete; useful tests exist, several claimed measured results are synthetic |
| 14 | Production infrastructure and controlled pilot | Scaffolding and activation controls exist; production rollout/acceptance unproven and technically incomplete |
| 15 | Operations, drift, retention, scale | Partial tooling plus ongoing obligations; cannot be called permanently 100% complete |

## 5. Detailed phase and subphase assessment

### Phase 0 — Product contract, policy scope, and engineering decisions

**What it does:** defines what the product is allowed to claim, which application/rule subset it supports, who may act, and what evidence is needed before deployment.

**Present:** requirements mapping; synthetic pilot scope; policy issue register; 12 ADRs; architecture and threat model; backlog, budget/dependency and testing documents; research/source/rule registers. Explicit restrictions prevent treating draft rules as authority for adverse action.

| Subphase | Status and completed work | Remaining work |
| --- | --- | --- |
| 0.1 Requirements and claims | Baseline exists with 34 requirements and the seven additions mapped | Refresh stale Phase-1-era statuses; identify actual named owners; link each requirement to current evidence and remaining gaps |
| 0.2 Policy/process decisions | 22 research records, unresolved policy issues, and synthetic correction process documented | Authoritative source-currency review; approved rule subset and interpretations; named policy/process sign-off, including cadre, intake, dates, rounding and response authority |
| 0.3 Architecture and data risk | ADRs, trust zones, privacy/retention classes and compatibility-spike tools present | Validate decisions against the implemented deployment and real model/provider scope; assign key/security/data owners |
| 0.4 Delivery and quality | Backlog, dependency register, target workload and test strategy exist | Update milestones based on actual gaps; approve representative benchmark data/splits and budget/onboarding ownership |

**Completion decision:** baseline deliverables substantially exist. An automated seed test cannot prove a policy workshop, signed decisions, or organizational agreement. Phase 0 is not fully accepted until those external records exist.

Evidence: `docs/phase-0/`, `docs/policy/POLICY_BASELINE.md`, `docs/architecture/adr/`, `docs/security/THREAT_MODEL.md`.

### Phase 1 — Repository, local platform, and delivery foundation

**What it does:** makes the backend installable, configurable, observable, and consistently checked.

**Present:** FastAPI composition; settings and safe error/health/build routes; Python dependency lock; non-root Docker targets; development/distribution scripts; Compose PostgreSQL, Temporal, S3 emulation, Keycloak, scanning, mail and observability configurations; synthetic seeds; CI/security/image publishing workflows; telemetry/redaction tests.

| Subphase | Status and completed work | Remaining work |
| --- | --- | --- |
| 1.1 Skeleton and boundaries | Implemented packages, interfaces, configuration, health/build and architecture-check tooling | Keep module documentation and release-scope descriptions aligned with later implementations |
| 1.2 Local environment | Bootstrap/start/check scripts and container definitions exist; relevant containers observed running during review | Verify a clean-machine start of the complete advertised stack and all identities; current running-container inventory alone is insufficient |
| 1.3 CI/supply chain | Pinned actions, lint/types/tests, security scanning and image SBOM/signing/attestation steps exist | Verify latest remote runs and branch/environment protection; distinguish registry publishing from deployment promotion |
| 1.4 Observability | Structured logs, redaction, trace propagation and dashboard/config assets exist | Exercise real cross-service traces, alarms, alert routing and production redaction/retention acceptance |

**Completion decision:** substantially implemented for local development. No remote CI history or full production telemetry evidence was obtained in this review.

**Fresh qualification failure:** `backend/tools/check_architecture.py` exits nonzero because multiple domain modules import SQLAlchemy/adapters and some import other domain modules directly. The quality workflow explicitly runs this gate, so passing lint/type checks does not establish passing CI on this tree. Either restore the documented architecture boundaries or approve a revised architecture and meaningful revised checks.

Evidence: `backend/pyproject.toml`, `Dockerfile`, `scripts/`, `infra/compose/`, `.github/workflows/`, `backend/src/workbench/platform/telemetry.py`.

### Phase 2 — Identity, authorization, and tenant isolation

**What it does:** gives institutions access to their own data and gives officers/auditors only explicitly assigned access.

**Present:** JWT verification and OIDC boundary; server-side actor/membership mapping; recent-MFA checks; scoped memberships/case assignments; immediate revocation; PostgreSQL security context and RLS; non-owner runtime roles; cross-tenant and unassigned-officer tests across multiple modules.

| Subphase | Status and completed work | Remaining work |
| --- | --- | --- |
| 2.1 Authentication/MFA | Token verification and privileged assurance checks implemented; fixture and OIDC configurations exist | Qualify production IdP/federation, lifecycle/revocation, real MFA and cloud identity behavior |
| 2.2 Object/action permissions | Central store/policy functions and route-level guards; tested deny paths | Extend adversarial coverage to combinations of same-institution case/run/evidence IDs, exports and new routes |
| 2.3 Database isolation | Role separation, RLS/security functions and transaction context implemented | Review against provisioned production roles and connection pools; independently verify all worker authority boundaries |
| 2.4 Assignment administration | Time-bounded grants/revocation and separation checks implemented | Exercise and document emergency access, scoped auditor assignment and organization approval operations with real administrators |

**Completion decision:** a strong local backend implementation. Production identity and independent isolation acceptance remain external gates; current tests do not justify a universal security guarantee.

Evidence: `adapters/auth.py`, `adapters/identity_service.py`, `adapters/domain_store.py`, `modules/identity_access/policy.py`, migration SQL and isolation tests.

### Phase 3 — Application domain, evidence metadata, and transactional audit

**What it does:** freezes what an institution submitted and ensures committed business changes have durable audit/work records.

**Present:** drafts/application history, slots and evidence versions, immutable revision manifests/hashes, expected-revision/idempotency commands, audit chains, transactional outbox, leases and stable workflow IDs, concurrency/rollback tests.

| Subphase | Status and completed work | Remaining work |
| --- | --- | --- |
| 3.1 Drafts/revisions | Application creation/update/submission/history and declared values implemented | Validate all intended categories, source-system references and duplicate-import scenarios beyond the synthetic slice |
| 3.2 Frozen manifests | Immutable submissions, exact evidence versions, hashes and concurrent submission behavior implemented | Qualify the response/replacement-evidence path with real later processing; retain canonicalization edge cases |
| 3.3 Audit/outbox | Atomic writes, chain verification, leased relay and idempotency implemented | Dispatch later domain events to their actual workflows; independently anchor/archive audit checkpoints |
| 3.4 History/summary | Stored-state history and summary endpoints exist | Validate pagination/query plans at target volume; bind frontend views and reconciliation to those actual endpoints |

**Completion decision:** the core local data backbone is substantially implemented. Generic intake receipts for later events do not constitute full downstream workflow integration.

Evidence: `adapters/application_service.py`, `adapters/domain_store.py`, `platform/outbox.py`, `processing/intake_worker.py`, `tests/test_intake_integration.py`.

### Phase 4 — Secure file intake and evidence delivery

**What it does:** receives hostile/untrusted uploads without exposing quarantine bytes as accepted evidence.

**Present:** upload sessions, expiry/type/size/checksum rules, version-specific quarantine references, actual ClamAV scan worker, network-isolated parser, accepted storage and previews, authenticated original/range/derivative delivery, access events and reconciliation code.

| Subphase | Status and completed work | Remaining work |
| --- | --- | --- |
| 4.1 Upload grants/quotas | Grants, checksum/version capture, ownership and quota checks implemented | Qualify any supported multipart/resume mode, large-media quotas, real S3 races and production bucket/IAM policies |
| 4.2 Isolation and acceptance | Real scanner/parser containers and rejection/fail-closed behavior implemented | Validate signature-update operations, image vulnerability status and resource limits under production workloads |
| 4.3 Authorized delivery | Original/preview/range delivery with permission and access records implemented | Complete actual report/frame delivery once those artifacts exist; exercise browser/content behavior and export disclosure |
| 4.4 Reconciliation | Orphan/stuck/upload consistency code and runbook exist | Schedule and monitor reconciliation in deployed environments; verify recovery without deleting referenced submitted originals |

**Completion decision:** strongest integrated implementation in the repository. Local S3 is an emulator; cloud durability/retention behavior and production policies require separate qualification.

Evidence: `processing/scan_worker.py`, `processing/inspect_file.py`, `processing/parser_runner.py`, `adapters/evidence_service.py`, `adapters/delivery_service.py`, `adapters/reconciliation.py`, `tests/test_file_intake_integration.py`.

### Phase 5 — Durable workflows and job operations

**What it does:** coordinates processing safely across retries, outages, long waits, cancellation and deployment changes.

**Present:** task-queue contracts, operation records/stable keys, activity receipts, timeout/retry policies, multiple workflow classes, cancellation/idempotency tests and mock-based workflow replay.

| Subphase | Status and completed work | Remaining work |
| --- | --- | --- |
| 5.1 Workflows/queues | Classes and input contracts exist; intake/scan run in actual shipped workers | Register/run real document, evaluation, connector, report, media and retention workers; wire domain events to them |
| 5.2 Retry/cancel semantics | Idempotent operation helper, receipts, retry policies and simulated failure tests exist | Replace fixed successful activity payloads; test real process death between commit and acknowledgement for each real side effect |
| 5.3 Deployment compatibility | Replay tests and sample patching/versioning exercise exist | Retain real production histories, replay actual implementations, rehearse mixed worker upgrades and history bounds |
| 5.4 Fairness/backpressure | Concurrency/admission helpers and queue contracts exist | Enforce and measure per-tenant/provider fairness, backlog alarms and operator controls with real workers under load |

**Critical implementation gap:** `activities/evaluation.py` returns `PASSED`, 12 evaluated rules and zero violations without invoking the evaluator. Reporting returns a report ID and four pages without rendering. Media returns a fixed frame count; retention reports `PURGED` with zero records. Source activity returns simulated verification. These are contracts/demo effects, not completed processing.

The worker-kill test raises a Python exception inside `ActivityEnvironment`; it does not itself kill an operating-system worker. Replay tests supply mock activities. Those tests remain useful, but their completion claims must be narrowed.

**Completion decision:** partial. Completing worker registration and replacing placeholder activities is one of the highest-priority tasks.

Evidence: `worker.py`, `processing/intake_worker.py`, `workflows/`, `activities/`, `tests/test_phase_5_workflows.py`, `tests/workflow_replay/test_workflow_replay.py`.

### Phase 6 — Document extraction, provenance, and versioned facts

**What it does:** converts evidence into reviewable facts while keeping the source, uncertainty and correction history.

**Present:** PDF digital-text geometry, classification/abstention, document-specific regex extractors, normalization/reconciliation, fact-set persistence and audited corrections. A PaddleOCR adapter and synthetic fallback provider exist.

| Subphase | Status and completed work | Remaining work |
| --- | --- | --- |
| 6.1 Text/geometry | Digital inspection, transforms and span/field structures implemented | Produce and securely serve reviewer page derivatives; verify exact source regions for every supported extractor |
| 6.2 OCR/extractors | Optional PaddleOCR adapter; synthetic OCR; initial certificate/land/intake/faculty/inventory/bandwidth extraction patterns | Install/pin model runtime and weights; rasterize scanned PDF pages before image OCR; qualify languages/templates and held-out confidence/abstention |
| 6.3 Normalization/claims | Unit/date/basis helpers and claims/provenance structures implemented | Expand real document boundary cases and entity/time-period reconciliation; validate all downstream fact mappings |
| 6.4 Corrections/frozen sets | New fact versions and correction auditing implemented | Automatically invalidate/recompute dependent runs; complete reviewer viewer and stale-result signaling |

**Specific gaps:** `ExtractionService.run_pipeline()` sends original document bytes into an OCR interface that opens an image; a scanned PDF must first be rendered page by page. The activity substitutes a synthetic PDF when content is absent instead of loading the pinned accepted object. Some field extractors use the first span as the source region, which does not prove exact localization. PaddleOCR is not a normal runtime dependency in `pyproject.toml`; fallback is expected in the base runtime.

**Completion decision:** partial, particularly for real scanned documents and provenance accuracy.

Evidence: `adapters/extraction_service.py`, `modules/extraction/ocr_provider.py`, `modules/extraction/geometry.py`, `modules/extraction/extractors.py`, `activities/extraction.py`.

### Phase 7 — Rule registry and deterministic evaluation

**What it does:** evaluates frozen facts under versioned sourced rules, explains calculations, and abstains when data or interpretation is insufficient.

**Present:** rule/source/interpretation import, 22 seeded records, versioned releases, typed rule operations, applicability logic, findings and run manifests, deterministic hashes, missing-input/cadre abstention, separate outcome dimensions and `adverse_action_allowed=False`.

| Subphase | Status and completed work | Remaining work |
| --- | --- | --- |
| 7.1 Registry/provenance | Sources, locators, versions, interpretations and safe demo seeds implemented | Independently approve source currency, interpretations and rule-coverage inventory |
| 7.2 DSL/resolution | Bounded evaluator and supported operations implemented | Validate unsupported/overlapping/superseded rules across intended categories and cycles; broaden boundary/property testing |
| 7.3 Evaluation/findings | Real pure evaluator and persistence/API path exist | Invoke it from real workflow activities; enforce frozen evidence/fact/source/release bindings throughout the upload path |
| 7.4 Policy examples | Worked demo vectors and ambiguity abstention tested | Obtain policy-owner approval and representative golden outcomes; expand beyond demonstration coverage |

**Completion decision:** substantive demonstration evaluator exists. Importing 22 records does not mean 22 fully approved, broadly applicable production rules. The normal background evaluation activity remains disconnected.

**Rule safety gap:** `RuleEvaluatorDSL.evaluate_rule()` handles abstention, thresholds, ratios and date-validity operations, then defaults to a generic `PASS` for other operations. Unsupported or incomplete rule expressions must be rejected or return `NOT_EVALUABLE`; they must not silently pass. This also limits the meaning of aggregate rule coverage.

The importer emits `generic_check` for remaining rule records, so this is relevant to the seed pack as well as future malformed rules. The printer seed expression uses approximately one printer per 30 computers, while the separate governance remedy example uses 5% of computers. Whatever interpretation the policy owner approves, all paths must use the same versioned definition rather than divergent embedded formulas.

Evidence: `modules/evaluation/`, `modules/rule_registry/`, `adapters/evaluation_service.py`, `adapters/rule_registry_service.py`, `tests/test_phase_7_evaluation.py`.

### Phase 8 — Historical records and authorized source verification

**What it does:** checks claims against historical/issuer evidence and distinguishes a conflict from an unavailable source.

**Present:** provider capabilities/simulators, six source states, observation records with simulation labels, outage/manual task path, officer confirmation and versioned historical import/reconciliation.

| Subphase | Status and completed work | Remaining work |
| --- | --- | --- |
| 8.1 Provider framework | Explicit simulator contracts/status mapping/capability labels implemented | Implement real credential, transport, limits, retries and freshness behavior for approved providers |
| 8.2 Historical imports | Hashed versioned record import/reconciliation implemented | Obtain authorized real records; qualify mappings, institution binding and coverage/staleness |
| 8.3 Signature/QR/manual paths | Synthetic signature cases, structured text/URL checks and audited manual confirmation exist | Implement cryptographic PDF/CMS verification, trust chains, byte-range integrity, revocation/time evidence and actual QR extraction/issuer response validation |
| 8.4 Live connector | Blocked connector contract explicitly reports missing access | Provider onboarding, authorization/consent, sandbox contracts and live adapter implementation |

**Important:** the signature engine recognizes PDF byte markers and synthetic revocation markers, then can return a simulated `VALID` with a fabricated issuer name. It does not prove a cryptographic signature is valid. QR destination allowlisting proves only a destination check, not document authenticity.

**Completion decision:** simulator/manual/history scope is implemented; live authentication is not. The plan explicitly permits a named blocked provider dependency, so the simulator is a legitimate intermediate deliverable, but must remain labelled.

Evidence: `modules/verification/simulator.py`, `service.py`, `signatures.py`, `modules/institutional_records/service.py`, `/api/v1/capabilities`.

### Phase 9 — Officer review, reports, and controlled rectification

**What it does:** lets officers disposition findings, request limited corrections, and compare reassessment with the frozen original.

**Present:** dispositions/pending tasks, officer/applicant disclosure-specific JSON reports with hashes, scoped/deadlined response windows, response manifests and finding-diff classifications.

| Subphase | Status and completed work | Remaining work |
| --- | --- | --- |
| 9.1 Review commands | Role/assignment-checked dispositions and pending-action APIs implemented | Complete stage/process-policy acceptance and user-facing review/inbox screens |
| 9.2 Reports | Stored immutable audience-specific JSON and disclosure policy implemented | Actual PDF templates/rendering/fonts/accessibility; stored object delivery; bind observations to the run's exact inputs |
| 9.3 Response windows | Scope, deadlines, rounds and stale/concurrent response checks exist | Qualify policy approval, replacement upload scanning and evidence ownership/version binding in a real response flow |
| 9.4 Reassessment/diff | Diff service handles resolved/unchanged/new/changed/not-evaluable cases | Re-extract replacement evidence, freeze new facts and run the actual evaluator server-side before computing the diff |

**Specific gaps:** `reassess_and_diff()` receives `reassessed_findings` from the request; it can create a new run identifier without executing a new evaluation. This is a diff facility, not proof of authentic recomputation. Report generation currently gathers observations for the institution rather than only the exact frozen run. The report activity's `RENDERED` status does not correspond to PDF rendering.

The lifecycle acceptance test directly inserts evidence/extraction/fact fixtures. It demonstrates service interactions on prepared state, not actual upload-to-OCR-to-report execution.

**Completion decision:** partial. Real reassessment and PDF generation are central remaining outputs.

Evidence: `modules/review/service.py`, `modules/reporting/service.py`, `modules/rectification/service.py`, `api/review_rectification.py`, `tests/acceptance/test_e2e_acceptance.py`.

### Phase 10 — Alerts, timers, access history, and audit views

**What it does:** makes pending work visible, schedules reminders/escalation, delivers notifications, and exposes evidence-access/audit history.

**Present:** semantic alert/task keys, task transitions, notification persistence/acknowledgement, timer records/generations and obsolete-timer cancellation, in-app/local SMTP paths, audit/access API and export/checkpoint records.

| Subphase | Status and completed work | Remaining work |
| --- | --- | --- |
| 10.1 Triggers/tasks | Deduplication and state-machine services implemented | Automatically derive all promised triggers/recipients from committed events; reconcile the separate task read models |
| 10.2 Durable timers | Schedule/cancel records and sample timer workflow exist | Run a real dispatcher; fire persisted deadlines into state changes/notifications; test replacement/extensions/timeout and timezone behavior |
| 10.3 Delivery/ack | In-app records and Mailpit SMTP attempt implemented | Container-safe SMTP configuration; approved recipient routing; robust retries/ambiguous outcomes; any production transport activation |
| 10.4 Audit/access/export | History APIs, access records, checkpoint/export data implemented | Verify chains before declaring export integrity; add independent signed archive/object delivery, archive lag alarms and frontend views |

**Specific gaps:** local email uses hard-coded `127.0.0.1:1025`, which refers to the API container itself when containerized, not the separate Mailpit service. Timer service code stores/cancels records but does not by itself process due timers. The sample workflow does not complete the persisted expiry/escalation/notification path. The checkpoint exporter hashes the collected events and labels integrity `VERIFIED` without invoking the separate audit-chain verifier.

**Completion decision:** partial. Persistence and direct command tests are ahead of automatic operational behavior.

Evidence: `modules/tasks_alerts/service.py`, `activities/timers.py`, `workflows/timers.py`, `modules/audit_access/service.py`, `adapters/audit_verifier.py`.

### Phase 11 — Media evidence and visible discrepancy analysis

**What it does:** inspects video/image evidence, detects candidate duplication, and assists a bounded room/equipment comparison without asserting fraud or complete inventory.

**Present:** role-specific duration policy, genuine image EXIF/average/difference hashes, Hamming comparisons, deterministic sampling timestamps, contact-sheet drawing utility, equipment correction records, and numeric floor-space reconciliation.

| Subphase | Status and completed work | Remaining work |
| --- | --- | --- |
| 11.1 Metadata/duration | Duration-policy and supplied-metadata persistence implemented; intake parser has ffprobe support | Derive analysis metadata from accepted uploaded bytes; do not trust client duration/codec claims as extracted evidence |
| 11.2 Frames/similarity | Sampling schedule, image hashes, matching and grid utility implemented | Decode actual video frames and store protected derivatives; replace synthetic hashes and blank contact-sheet thumbnails; calibrate benign false flags |
| 11.3 Equipment counts | Synthetic/heuristic boxes, advisory text and human correction persistence exist | Use a licensed validated detector, or a clear manual-only comparison with no fabricated detections/confidence/coverage |
| 11.4 Integration | Media APIs, persisted results and access tests exist | Wire actual processing into tasks/reports/claims and versioned evidence delivery; qualify similarity scope and retention |

**Specific gaps:** video rows use Python `hash()` on evidence ID/timestamp rather than actual frame pixels. That hash also varies across interpreter processes. The contact-sheet endpoint creates blank colored images. Equipment code lays out six boxes from image dimensions, or estimates a count from the declared quantity; it does not inspect equipment pixels. Fixed 65% coverage and YOLO-like model names are not measured model output. Floor-plan service compares caller-supplied identified spaces; it does not extract geometry from a drawing.

**Completion decision:** partial/simulated. The plan permits an explicit manual fallback, but canned detections must not be presented as real inference. A manual fallback should show the actual evidence and an attributed human observation.

Evidence: `modules/media_analysis/service.py`, `api/media_spatial.py`, `activities/media.py`, `tests/test_phase_11_media_spatial.py`.

### Phase 12 — Rule-change governance, replay, and remedy scenarios

**What it does:** supports independent approval of rule changes, before/after impact, reproducible history, and limited advisory remedies.

**Present:** candidate/release manifests and hashes, author/approver separation, qualification-gate/publication APIs, hypothetical amendment demonstration, stored historical runs, bundle hashing CLI and remedy arithmetic examples.

| Subphase | Status and completed work | Remaining work |
| --- | --- | --- |
| 12.1 Candidate impact | Candidate validation, simulated outcomes and impact categories implemented | Use the main evaluator/DSL on authoritative frozen inputs; reject unsupported rules and require missing-input abstention |
| 12.2 Approval/publication | Dual-control and immutable release machinery implemented | Bind real approved sources/interpretations/regression evidence and named approvers; qualify production activation and stale-approval paths |
| 12.3 Offline replay | Bundle creation and file/manifest hash verification CLI implemented | Include executable rule/evaluator material and canonical outputs; actually re-evaluate offline and compare; authenticate the checkpoint/root and validate required manifest entries |
| 12.4 Remedies/scenarios | Bandwidth/printer/certificate examples and no-approval disclaimer exist | Re-run scenarios through the same evaluator; derive closed/remaining findings from results and enforce approved stage/scope policy |

**Specific gaps:** candidate simulation uses a separate small `_evaluate_single_rule()` with `PASS` as the default for unknown rule IDs. Remedies hard-code a passing re-evaluation and example finding IDs rather than running the evaluator. The offline CLI verifies hashes; it does not reproduce rule execution. These are materially narrower than the planned reproducibility and same-engine scenario gates.

The replay-export endpoint additionally supplies fixed example facts, evidence and source observations instead of packaging the selected run's actual frozen inputs. Publication uses a fixed timestamp. Replace those fixtures before calling these exports historical reproducibility evidence.

**Completion decision:** partial; governance structure is useful, computational consistency and reproducible execution need completion.

Evidence: `modules/rule_governance/service.py`, `api/rule_governance.py`, `adapters/rule_registry_service.py`, `cli.py`, `tests/test_phase_12_rule_governance.py`.

### Phase 13 — System qualification, security, and measured evaluation

**What it does:** proves the supported system meets security, quality, throughput and recovery expectations using actual measurements.

**Present:** acceptance/failure-injection tests; OWASP-labelled security tests; metric/CI utilities; ten synthetic benchmark manifest entries; k6 profiles; capacity/cost model; database invariant/reconciliation drill tool.

| Subphase | Status and completed work | Remaining work |
| --- | --- | --- |
| 13.1 End-to-end/failures | Prepared-state lifecycle and injected-failure tests implemented | Add real submitted-upload-through-worker/report/media/response acceptance; kill actual relevant processes and exercise real side-effect recovery |
| 13.2 Security/privacy | Automated authorization/upload/SSRF/redaction/integrity examples exist | Independent scoped security/privacy review, remediation record and named residual-risk acceptance; broaden gaps revealed by this review |
| 13.3 Benchmarks | Reporting structures, confidence calculations and synthetic manifests exist | Execute actual extraction/evaluation/media pipelines against frozen ground truth; compute metrics from predictions, with data strata and simulation exclusions |
| 13.4 Load/cost/recovery | Load scripts, assumed cost calculator and invariant drill exist | Run and retain load/fairness/cost measurements; restore database, object versions, keys and Temporal into recovery environment and measure RPO/RTO |

**Critical finding:** the benchmark runner assigns counts such as 39/40 digital fields, 19/20 scanned fields, 49/50 requirement agreements and fixed timing arrays. It does not derive those values by executing the pipeline against ground truth. Confidence intervals around invented observations are not empirical qualification. Human effort reduction is correctly marked unmeasured, but other claimed measurements need the same honesty.

The recovery tool checks database conditions and advances a cursor; it does not establish recovery from a real database/object/workflow backup. Capacity/cost numbers use configured assumptions and must be labelled estimates, not measured deployment economics.

**Completion decision:** incomplete. Passing contract tests cannot substitute for the plan's measured qualification exit gate.

Evidence: `benchmarks/evaluation/runner.py`, `benchmarks/manifests/packet_manifests.json`, `benchmarks/load/`, `backend/tools/capacity_cost_model.py`, `backend/tools/recovery_drill.py`, `backend/tests/security/`, `backend/tests/acceptance/`.

### Phase 14 — Production infrastructure and controlled pilot rollout

**What it does:** provisions an operable environment and admits real pilot users/data only after scoped acceptance.

**Present:** Terraform modules for networking/security/database/storage/ECS/telemetry, integration/staging/production environment scaffolds, release artifacts, static infrastructure/migration checks, pilot scope restrictions and operational runbooks.

| Subphase | Status and completed work | Remaining work |
| --- | --- | --- |
| 14.1 Infrastructure/isolation | Foundational resources, task definitions, IAM/security groups and environment templates exist | Complete ECS services, load balancer/listeners/targets, commands/config/secrets per unit, state/locking, required endpoints and deploy/validate evidence |
| 14.2 Release/migrations | Image build/scan/sign/publish workflow and migration tools exist | Real environment promotion, migration jobs, canary traffic/health rollback and mixed-version worker qualification |
| 14.3 Pilot onboarding | API/database gates restrict scope to synthetic/advisory operation | Approved cohort/data/consent, policy pack, actual reviewers/providers/recipients and pilot protocol |
| 14.4 Operational acceptance | Sixteen runbooks and go/no-go checklist exist | Named duty/support owners, working alarms/backup/rotation, signed pilot-entry decision and measured pilot results |

**Specific gaps:** the ECS module defines task definitions but no ECS service resources or load balancer resources were found. Units share an image without per-unit command overrides, and only generic environment variables are supplied there; this does not run eleven distinct backend roles. The release workflow publishes images but does not deploy/promote them into three cloud environments. `rehearse_rollback.py` changes an in-memory traffic dictionary and prints compatibility statements; it is not an actual canary/rollback rehearsal. `check_infra.py` checks file presence and selected text, so its passing result does not prove provisioned trust-zone behavior.

**Completion decision:** production rollout is unproven and technically incomplete. Pilot activation controls are an implemented safety feature; their tests do not demonstrate a real pilot.

Evidence: `infra/terraform/`, `.github/workflows/release.yml`, `backend/tools/check_infra.py`, `backend/tools/verify_migrations.py`, `backend/tools/rehearse_rollback.py`, `backend/tests/acceptance/test_phase_14_pilot.py`, `docs/runbooks/`.

### Phase 15 — Operations, improvement, and scale decisions

**What it does:** keeps the service safe and correct as workload, rules, source access and document templates change.

**Present:** operational summaries, containment/release and reconciliation commands, access sweeps/review summaries, retention policy/hold/eligibility/purge APIs, purge manifests and champion/challenger demonstration.

| Subphase | Status and completed work | Remaining work |
| --- | --- | --- |
| 15.1 Service operations | Health, containment and reconciliation tooling implemented | Operate the real deployment, capture SLO/incident/action records and repeat actual outage/restore exercises |
| 15.2 Regulatory/model drift | Rule/version infrastructure and drift report interface exist | Monitor authorized amendments; run real champion/challenger extractors on frozen documents; replace hash-derived synthetic correctness with measured predictions |
| 15.3 Access/retention/providers | Access expiry sweeps, legal holds and purge eligibility implemented | Complete storage/version deletion assurance, legal-hold synchronization, deletion failure/race handling, credential rotation/provider assurance and approved operating cadence |
| 15.4 Scaling/architecture | Cost/capacity assumptions and architecture decisions documented | Gather trends/bottlenecks, forecast actual demand, approve scale changes and rehearse migration/rollback as needed |

**Retention gaps:** the actual purge service deletes original-evidence database rows without deleting their original storage objects. Derivative object deletion exceptions are suppressed before metadata deletion; object deletion success is therefore not assured. Eligibility is calculated before the purge transaction, so legal-hold/dependency changes need revalidation at execution. The workflow activity separately reports a placeholder purge result. Real safe purge needs version-specific manifests, storage receipts, failure recovery and race tests.

**Drift gap:** the analyzer calculates champion/challenger correctness using Python `hash()` and synthetic thresholds. It does not run either model, and results are not stable across interpreter hash seeds.

**Operator precision gaps:** provider containment currently pauses all source-verification operations rather than filtering by the supplied provider target. The operational storage-reconciliation branch reports derivatives with missing object keys as healthy without checking object storage. Narrow those commands and prove actual recovery effects before operational qualification.

**Completion decision:** partial operational tooling plus ongoing work. The original plan explicitly defines this as an ongoing operating phase, contradicting a permanent “100% complete” conclusion.

Evidence: `modules/operations/`, `modules/retention/`, `activities/retention.py`, `tests/test_phase_15_operations_retention.py`, `docs/handover/HANDOVER_PACKAGE.md`.

## 6. Completion claims that should be corrected

| Existing claim/evidence | Why it needs qualification | Recommended wording/action |
| --- | --- | --- |
| `docs/PHASE_AUDIT.md` labels every phase PROVEN | Some listed tests validate mocks, supplied records or narrower service behavior | Split code, direct-service tests, integrated runtime, measured qualification and external acceptance |
| `docs/development/PHASE_15_VERIFICATION.md` says 100% complete | Purge/drift/workflow gaps remain; phase is ongoing by definition | “Operational tooling implemented for synthetic/local scope; listed production and operating gates remain” |
| `docs/development/PHASE_14_VERIFICATION.md` says complete/qualified | Terraform/static and in-memory rehearsal cannot demonstrate rollout | Report scaffold/static-check status separately from provisioned/deployed/accepted status |
| Phase-0 capabilities say Phases 2–15 are only placeholders | Later domain code now exists | Refresh rather than use this old baseline as the current project state |
| Benchmark metrics described as measured/qualified | Counts and time arrays are fixed in code | Mark as illustrative until actual pipeline predictions/timings are collected |
| Signature VALID/integrity verified | Simulated byte-marker logic | Keep visibly synthetic; implement cryptographic validation before authenticity claims |
| Video contact sheet/frame extraction called real | Blank tiles and metadata-derived hashes | Decode/serve actual frames, or label demonstration placeholders |
| Equipment YOLO-like model/version/confidence | No actual detector invocation in the service | Remove unsupported model identity/quality claims; implement real detector or explicit manual-only path |
| Replay CLI proves reproduction | It checks bundle hashes only | Call it integrity verification until evaluator execution/output comparison is added |
| “Seven additions” sign-off in Phase-13 document | Its seven rows differ from the plan's actual seven additions | Restore exact mapping below, with evidence and gaps for each |

The current working tree had existing staged modifications when review started. They were preserved. Historical test outputs in documentation are treated as recorded claims, not fresh results from this review.

## 7. Actual seven requested additions

| Addition in the implementation plan | Implemented scope | Remaining |
| --- | --- | --- |
| 1. Video metadata/duration/duplicates/geotags | Duration rules, EXIF utilities, metadata records, timestamp schedule | Real decoded frame pipeline/contact sheets; measured similarity calibration |
| 2. Triggered alerts/recipients/timers/dedup | Alert/task/notification/timer services | Automatic trigger routing, working durable dispatch/escalation, container-safe mail and recipient control |
| 3. Officer/applicant reports and rectification | Audience JSON, scoped response windows, diff logic | PDFs and real replacement-evidence reassessment |
| 4. Document view/download logging | Delivery permission/range/access-event implementation | Extend consistently to actual report/frame exports and production delivery paths |
| 5. Audit history and pending-action screens | Backend APIs and stored task/audit data | Frontend screens; end-to-end task synchronization and authenticated checkpoint archive |
| 6. Visible discrepancy check | Synthetic equipment demonstration and human correction records | Validated real inference or clear manual-only evidence comparison |
| 7. Separate completeness/source/forensic outcomes | Explicit status models, evaluator separation and tests | Carry separation through the real fully integrated runtime, reports and UI |

## 8. Recommended remaining-work sequence

1. **Correct rule safety, CI and claim/status documents.** Unsupported rule operations must abstain or reject rather than pass. Resolve the failing architecture gate. Record actual versus simulated behavior and named external gates. Do not use fixed benchmark numbers or synthetic detections as success evidence.
2. **Complete one real vertical slice.** Upload a supported digital/scanned document, scan it, fetch its pinned accepted bytes, extract real facts, evaluate a scoped rule pack, generate audience JSON/PDF, create a real pending task, accept a scoped replacement, recompute and show the diff. Retain actual outputs.
3. **Connect the background runtime.** Register actual workers/activities, map events to workflows, remove fixed success results, keep workflow histories reference-only and persist actual side-effect receipts.
4. **Finish document processing and reporting.** Rasterize scanned PDFs, package OCR/models, qualify exact source boxes and supported languages; render/access-check/store PDFs.
5. **Make uncertainty features honest and useful.** Genuine signature verification; real video decoding; explicit manual equipment fallback until qualified inference exists; derive source state from actual provider/manual evidence.
6. **Unify governance computations.** Candidate impact, remedies and replay must use the same evaluator and authoritative frozen inputs. Unsupported rules must abstain/reject, not default to pass.
7. **Finish operational correctness.** Timer dispatch, notification routing, verified/signed audit archives, version-specific safe purge with hold/dependency rechecks and reliable deletion receipts.
8. **Build the first-party user experience.** Applicant submission/status/response, officer evidence/provenance/review, task/audit views, and separately permissioned rule administration. Use actual APIs throughout.
9. **Replace synthetic qualification with measurements.** Frozen representative ground truth, actual predictions/timings, fairness/load tests, independent security assessment, real backup/restore and rollback with achieved RPO/RTO.
10. **Complete and accept cloud/pilot deployment.** Finish IaC runtime/service wiring and promotion pipeline, obtain named policy/provider/data/operations approvals, run the approved advisory cohort and review measured results before expansion.

Items 2–7 are engineering gaps. Provider access, authoritative rule interpretation, real-data approval, independent review and pilot acceptance are separate external dependencies. They should be tracked with named owners rather than disguised as coding tasks or test passes.

## 9. Verification performed in this review

Fresh local check results and exact limitations are recorded below after execution. Test counts describe the current checkout and current run, not a production guarantee.

| Fresh check | Result | Interpretation |
| --- | --- | --- |
| Ruff check: `backend/src`, `backend/tests`, `backend/tools`, `backend/migrations` | PASS | The checked Python files satisfy their configured lint rules |
| Ruff format check for the same directories | PASS; 226 files already formatted | Formatting only |
| Mypy strict configuration over `backend/src/workbench` | PASS; 144 source files | Static typing only |
| `backend/tools/check_repository.py` | PASS | Repository baseline checks only |
| `backend/tools/check_architecture.py` | FAIL; 29 violations in 12 files | Existing CI gate is not satisfied; domain/framework/infrastructure and cross-module imports violate it |
| `backend/tools/check_infra.py` | PASS | File/string checks only; no provisioned infrastructure verified |
| `backend/tools/verify_migrations.py` | PASS | Static revision/add-column checks; no rolling deployment or restore proved |
| Foundation API/config/bootstrap/telemetry/trace test group | 21 passed, 1 warning | Fresh focused run in 3.66 seconds |
| Real file-intake integration group with `WB_FILE_INTEGRATION=1` | 15 passed, 2 skipped, 2 warnings | Fresh scan/storage/delivery checks in 66.29 seconds; the two skipped cases deliberately stop local parser/relay services and were not enabled |
| Seed database integration test with the actual configured local URL | 1 passed, 1 warning | Two seed institutions, 22 disabled draft rules checked |
| Read-only unsupported-rule probes | Unsupported DSL operation returned `PASS`; unknown candidate rule returned `PASS` | Confirms the silent-pass correctness gap |
| Read-only signature probe using marker-only PDF bytes | `VALID`, `simulated=True` | Confirms this is a signature simulator, not cryptographic verification |
| Additional root `scripts/check_secrets.py` lint/format check | FAIL; 7 lint findings and formatting differences under the invoked default/root configuration | Ancillary script hygiene; distinct from the backend lint result |

**Full-suite limitation:** the repository records an earlier `179 passed` run in its audit document. This review does not independently reproduce that result. The interrupted launch left duplicate pytest processes; they were stopped and a single suite was restarted with the actual configured database URL loaded without printing credentials. The clean attempt progressed beyond 40% but was stopped after prolonged database execution. A read-only `pg_stat_activity` inspection observed an active membership lookup lasting more than 100 seconds, without a lock wait reported in that snapshot. The cause needs separate query-plan/test-isolation investigation; it is not established as a functional application failure or a production-capacity result. No fresh full-suite success is claimed.

An earlier exploratory attempt used a non-URL marker for the integration variable and therefore failed the seed test that consumes that variable directly. The corrected isolated seed check passed. Abandoned/contending attempts are not reported as trustworthy product failure counts.

Completed focused-run XML evidence is retained in ignored local files:

- `.local/project-analysis-unit-tests.xml`
- `.local/project-analysis-file-tests.xml`
- `.local/project-analysis-database-test.xml`

The tests created synthetic fixtures in the already configured local development database. No application source, existing staged changes, production configuration, cloud environment or external provider was changed by this analysis. The only intentional tracked-content addition is this review document.

