# NiyamFlow verification results

Date: 30 October 2026. Problem statement: SIH26262.

## Outcome

The core approval/compliance prototype is implemented and has been exercised against real PostgreSQL row-level policies and authenticated FastAPI routes. It includes a browser workspace and a synthetic demo seeded through the running HTTP API. This is development verification, not production qualification, official policy validation or proof of real-world time savings.

## Executed checks

| Check | Result | Scope |
| --- | --- | --- |
| Complete backend regression suite | 199 passed, 17 skipped | Existing phases and the initial NiyamFlow acceptance scenarios, using the dedicated PostgreSQL review database. |
| Final NiyamFlow acceptance run | 16 passed | Latest workflow, report-clock, template, session and acknowledgement refinements. |
| Final roster visibility regression | 1 passed | Legacy regional officers and supervisors cannot read another region's roster. |
| Ruff | Passed | Backend source, migrations, NiyamFlow tests and demo seed tool. |
| Strict mypy | Passed, 160 source files | Entire backend source tree. |
| Module architecture checker | Passed | Pure domain contracts remain separate from adapters/frameworks. |
| Browser JavaScript syntax | Passed | Node syntax check of the actual workspace script. |
| Browser inspection | Passed for inspected scope | Final navigation/layout and safe rejection of an invalid access token. Full manual interactions for every authenticated role were not performed in the browser. |
| Running API demo seed | Passed | Actual HTTP calls independently drafted/published the demo pack, submitted intake, created a case and renewal watch, and recorded an online roster. |

The 17 targeted NiyamFlow tests overlap with tests in the full regression run. Do not add these counts and describe them as one larger suite. The complete regression was followed by focused checks after the final refinements.

The 17 skipped regression checks comprise 15 complete local file/scan-stack checks and two opt-in outage probes. They were not enabled or claimed as executed.

## Critical behaviors established

1. Ambiguous route selectors and non-authority decision stages are rejected by the process-pack validator.
2. Total elapsed time is retained while recorded authorized pause intervals affect only the operational accountability clock.
3. Cross-institution case access fails. Institution users cannot perform officer transitions, stale revisions fail, and ordinary supervisors cannot substitute for a delegated competent authority.
4. Independent author/approver publication is exercised. The fixture models all four named route families while keeping SHC and SAC separate.
5. Uploading renewal evidence leaves accepted expiry unchanged. Only authorized verification promotes the replacement evidence/expiry. The watch remains accessible after case closure.
6. Deadline generations suppress obsolete work and repeated activity execution does not duplicate alerts. In-app acknowledgement does not close an undertaking.
7. Concurrent confirmations sharing a member across different committees produce one success and one conflict. A database trigger checks overlaps outside the planner's visible row set as well.
8. Queue, scheduling, visit/report milestones are distinct. An actual-completion-based report clock starts at recorded completion. A case requiring an accepted report cannot advance prematurely.
9. Competent-authority delegation can enable the decision stage, and revocation removes the delegated access. Continuing duties are not closed by the application decision.
10. Renewal upload permits enable a bounded response through the existing intake guard without reopening intake or changing accepted validity. Expired permits fail.
11. Delegated committee members can use the existing audited evidence HEAD/delivery authorization boundary only with the appropriate assignment and fresh MFA; unrelated institutions are denied.
12. Each of the six report families returns scoped records and a snapshot hash. Governance templates generate a draft without issuing a notice or changing the case revision.
13. New workspace session capabilities distinguish institution response, processing and publication roles. Roster read scope remains regional even for legacy role labels.
14. Outbox recovery no longer fills its batch with already-unleased traffic while expired leases wait. Expired owned leases are ordered and row-locked with `SKIP LOCKED`.

Clean evidence objects in the acceptance fixture are constructed by the database owner as synthetic preconditions. These tests do not establish that an actual uploaded file passed S3 storage, ClamAV scanning or external signature verification.

## Files and components

- `backend/src/workbench/modules/approval_workflow/policy.py`: validated policy graphs, source-linked configuration, clock helpers and template boundaries.
- `backend/src/workbench/adapters/niyam_tables.py`: approval-domain metadata.
- `backend/src/workbench/adapters/niyam_service.py`: transactional workflow, evidence review, planning, clocks, summaries, drafts and reporting.
- `backend/src/workbench/api/niyamflow.py`: authenticated API contracts and workspace permission projection.
- `backend/src/workbench/web/niyamflow.html`: responsive API-backed workspace with in-memory session handling and cached-record clearing on disconnect or failed identity switch.
- `backend/src/workbench/activities/niyamflow.py` and `workflows/niyamflow.py`: generation-checked durable follow-up.
- `backend/migrations/versions/0019_*` through `0024_*` and `backend/migrations/sql/niyamflow_0019.sql`: RLS, ownership, publication and booking integrity.
- `backend/fixtures/niyam_demo_pack.json`: illustrative policy with four route families and communication drafts.
- `backend/tools/seed_niyam_demo.py`: loopback-only synthetic demonstration through real authenticated APIs.
- `backend/tests/test_niyamflow.py`: the 17 domain acceptance/regression tests.

Existing evidence upload/delivery, outbox dispatch, lifecycle worker registration, API composition and operator reconciliation were connected or corrected rather than replaced. Previous uncommitted project work was retained.

## Review environment and evidence

Verification used the separate local database `phase_review_niyam` on the existing dedicated review PostgreSQL cluster. The configured main application database and `.env` were not migrated or overwritten. Test records and synthetic demo records remain in the review database for inspection.

Task-local execution evidence is retained in:

- `.local/niyam-full-tests.xml` and `.local/niyam_full_tests.log`;
- `.local/niyam-acceptance-tests.xml` and `.local/niyam_acceptance_tests.log`;
- `.local/niyam-roster-scope-tests.xml` and `.local/niyam_roster_scope_tests.log`;
- `.local/niyam_seed_result.json` for the synthetic HTTP demonstration references.

These are local development artifacts, not committed production evidence or a public benchmark dataset.

## Remaining production work

Use the [implementation guide](NIYAMFLOW_IMPLEMENTATION.md) for startup and scope. Production readiness still requires current authoritative route/deadline policies, business-day/holiday calendar support where applicable, real institutional/committee integrations, an end-user SSO flow, verified notification delivery, a live Temporal recovery/soak run, external file-stack tests, accessible role-by-role UI completion, representative workload testing and stakeholder acceptance.

The prototype deliberately uses a scheduling heuristic rather than claiming an unvalidated CP-SAT advantage. It does not automate statutory verification, substitute for authorized committee membership, infer certificate validity without a source, or claim a competition outcome.
