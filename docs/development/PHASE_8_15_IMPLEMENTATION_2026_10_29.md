# Phases 8–15 remediation implementation

Implemented 29 October 2026 in response to the [implementation review](PHASE_8_15_REVIEW_2026_10_29.md). This record supersedes earlier unconditional completion/qualification statements. It describes working local capabilities and their verification; it does not certify a deployed production service.

## Changes delivered

| Phase | Implemented changes |
| --- | --- |
| 8 | Replaced byte-marker signature success with offline cryptographic PDF inspection using pyHanko. Unknown issuer authorization or unavailable revocation evidence cannot become VALID. QR destinations require HTTPS, an approved host, no embedded credentials, and the standard port; a safe destination alone does not prove authenticity. Signature result simulation flags now reflect the actual validator. |
| 9 | Officer-report authorization at API and PostgreSQL RLS layers; applicant listings exclude officer reports. Report inputs use the evaluation's frozen source snapshot, with true provider labels. Stable PDF rendering, readable text order, download hash and audit event. Scoped replacement evidence is validated against application, slot and admission status. Response submission locks/checks the window and current revision, preserves the original, creates a new revision and enqueues real reassessment. The worker reads hash-checked object versions, extracts supported replacements, freezes a new fact set, evaluates and stores a diff. Diffs read finalized stored outcomes and require valid revision lineage; callers cannot supply findings or resolve deficiencies merely by omitting them. Replayed response processing returns the existing run. |
| 10 | Timer and email intent are committed to the outbox. Registered workflows and worker entry points dispatch those intents. Due timers check cancellation and generation before making a task or expiring a window; replay does not repeat the transition. Submission cancels obsolete response reminders. Deadline extensions rebuild the workflow wait. Email state becomes UNKNOWN before SMTP, avoiding blind duplicate retries after ambiguous failures. Response and reassessment audit events preserve the case trail. |
| 11 | Isolated media processing reads admitted object versions, verifies hashes, probes real video duration/codec/dimensions, decodes bounded real frames and computes content hashes. Contact sheets contain the decoded images, are stored as versioned derivatives, and are integrity-checked when served. API requests enqueue processing rather than accepting client metadata as analysis. Removed fabricated detection grids, invented YOLO identity, confidence and coverage. Equipment comparison explicitly enters manual fallback; authorized officers record auditable counts without rewriting the original result. |
| 12 | Replay verifies the exact manifest-bound file/hash set and rejects detached hash lists, missing/extra files and changed bytes. Newly exported runs include actual frozen executable inputs and outcomes; offline verification re-executes rules and compares outputs. Legacy runs lacking snapshots are rejected rather than populated with invented facts. Impact simulation uses stored frozen facts and no seeded substitute packet. Scenarios share the evaluator DSL, abstain on unsupported/missing inputs and compute actual post-remedy outcomes. Intake optimization requires a separately approved interpretation. Publication is bound to the independently approved content hash and uses real publication time. Canonical person identities enforce separation of duties. |
| 13 | Removed fixed benchmark accuracy/timing claims and hash-derived drift predictions. Benchmark aggregation accepts captured observations and reports unmeasured categories explicitly. Drift compares frozen ground truth with actual versioned prediction captures; absent captures block measurement. Added regression and PostgreSQL acceptance coverage, including real video decoding, report RLS, revision lineage, offline replay, timer replay and ambiguous mail outcomes. |
| 14 | Added explicit worker commands, configurable secret injection, CloudWatch log groups, gated ECS services with deployment circuit breakers, and optional TLS ALB/listener/target-group resources. Environment modules expose activation inputs; services remain dormant until configured. Added a media Docker target and Compose lifecycle/media workers. Rollback tooling now calls ECS, waits for convergence and verifies the running baseline instead of printing simulated success. Database compatibility is reported separately as unmeasured. |
| 15 | Legal hold changes and purge execution share a transaction lock. Eligibility is evaluated in the deletion transaction and includes frozen manifest/foreign-key dependencies. Object deletion uses exact versions; failures are no longer swallowed before deleting metadata. Original purge also deletes its quarantine/clean objects and derivative objects. Dry runs claim zero freed bytes. Recovery tooling labels reconciliation checks separately from a restore drill. Operational timestamps are timezone-aware. |

Persistence/orchestration classes have moved from `modules/*/service.py` to `adapters/*_application_service.py`. Domain packages expose pure contracts and behavior. The architecture checker continues to reject framework/adapter imports from domain modules and cross-module implementation imports, while allowing explicit public package interfaces. Internal Python imports changed; HTTP route names remain available, with the intentional asynchronous media and server-controlled reassessment contracts described above.

## Database and runtime changes

- Migration `0017_review_integrity.py`: restrictive report audience policies, one submission per response window and one open window per application.
- Migration `0018_worker_read_models.py`: explicit worker input/read-model privileges and supervisor case access consistent with the API authorization contract. Workers retain non-owner, non-BYPASSRLS credentials.
- Runtime dependencies `pyhanko` and `reportlab` are now included in the lockfile's application dependency set.
- `python -m workbench.processing.lifecycle_worker` consumes the `lifecycle` queue for timers, notifications and rectification.
- `python -m workbench.processing.media_worker` consumes `media-processing`; use the Docker `media` target so ffmpeg/ffprobe are available. Processing is bounded to one concurrent decode per worker.
- The outbox relay must run alongside those workers. The Compose file now declares both workers; the development scripts build `sih-workbench:media` along with the runtime/parser images.
- `POST /evidence/{id}/media-analysis` returns a queued event ID. Query the existing media-analysis endpoint after processing; the contact-sheet endpoint serves the stored derivative.
- Reassessment is enqueued when the applicant submits a response. `POST /rectification/reassess` returns QUEUED until a stored reassessment exists, or reads a supplied stored run after lineage checks.

## Verification and reproducibility

Fresh isolated native PostgreSQL 18 databases were created under the ignored `.local/phase-review-pg` directory, listening only on `127.0.0.1:55432`. All migrations were applied; role-provisioned API/worker tests executed against these databases. The configured project database and `.env` were not changed. Test fixture objects are synthetic; storage/SMTP behavior is mocked in tests requiring those transports. The real video test invokes installed ffmpeg/ffprobe.

The reproducible runner is `backend/tools/run_phase_review_tests.py`. Point `WB_REVIEW_DATABASE_URL` at a pre-created local database whose name starts with `phase_review_`, then run from the repository root:

```powershell
backend\.venv\Scripts\python.exe backend/tools/run_phase_review_tests.py
```

The runner provisions development runtime roles, migrates, seeds and runs pytest without modifying `.env`. Run it against a fresh database for a clean qualification record. Synthetic tests use the configured local artifact transports only when explicitly enabled; the scanner/storage full-stack tests remain separate.

Final full-suite result on a fresh PostgreSQL database after the architecture refactor: **186 passed, 17 skipped, 2 deprecation warnings** in 131.91 seconds. The 17 skips require the Docker scanner/storage stack and opt-in outage probes. The 19 focused review regressions passed separately. Strict mypy passed for 153 source files. Ruff lint/format, repository checks, architecture checks, migration-chain checks, and the static infrastructure checker passed. All 27 Terraform files and the Compose YAML parsed successfully.

The JUnit execution record is `.local/phase-review-tests.xml`. Ruff checks/formatting, strict mypy, repository checks, domain architecture checks and migration-chain checks were also run. Terraform files were syntax-parsed and the repository static infrastructure checker was run; this is not `terraform plan/apply` or evidence of deployed infrastructure. The migration safety tool's static output is not evidence that old workers were actually exercised during a cloud rollout.

## Remaining qualification gates

These require real external inputs or operating evidence and must stay visible:

1. Issuer/provider onboarding, authorized credentials and real sandbox/production contract evidence. Source providers remain explicitly simulated.
2. An approved issuer trust bundle, issuer-to-claim authorization policy and current revocation material. Offline integrity inspection alone cannot authorize an issuer.
3. Approved benchmark datasets and captured extraction/model predictions, measured quality/performance/cost and any human-effort study. No fixed scores substitute for these records.
4. The Docker scanner/storage stack, real Temporal server failure/restart exercises and object-store integration. Direct worker activities and PostgreSQL replay/idempotency checks do not certify those external runtimes.
5. Environment-specific TLS, OIDC, secrets, database/Temporal endpoints, per-unit images, worker networking and IAM review; actual Terraform provider validation/plan/apply; staging rollout/rollback and database/object/workflow restore evidence.
6. Named policy/security/service-owner pilot approval, independent security review and ongoing operational/access/provider/retention reviews. Phase 15 remains an ongoing operating phase.

Do not remove the staging/production configuration block or enable live/outbound pilot capabilities solely because local tests pass. The ECS rollback command requires a real approved cluster/service and immutable baseline task-definition ARN; it was not executed against AWS during this work.
