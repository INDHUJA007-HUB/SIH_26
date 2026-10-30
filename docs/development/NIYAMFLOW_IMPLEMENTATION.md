# NiyamFlow implementation and prototype guide

Prepared 30 October 2026. Target: SIH26262.

## What changed

The repository now contains a working approval-domain prototype on top of the existing evidence workbench. It is no longer only a proposal document. The submitted Word review was assessed as supporting material; its unsupported completeness percentages and competition guarantees were not adopted.

The implementation covers:

- Published, hashed process-pack versions, independent author/approver roles and a validated route graph. Running cases pin the published pack.
- Category-to-route selection with an explicit failure for an unknown category, guarded transitions, reasons for returns, revision checks and idempotent commands.
- Separate scrutiny, re-scrutiny, EVC, SHC, SAC and competent-authority stages where configured. The demo pack contains the four named route families and distinct hearing/appeal branches.
- Case summaries and deterministic communication drafts from templates in the published pack. Draft generation does not issue an official notice or change a decision.
- Undertaking and document-validity records with separate review state, computed time condition and escalation/reminder history. Responses do not close conditions or change accepted validity.
- Independent officer verification, evidence ownership checks, clean-evidence requirements, preserved accepted versions and continuing obligations after case closure.
- Bounded permits to upload renewal evidence through the existing quarantine/intake pipeline after original application submission. Upload permission does not extend document validity or reopen intake.
- Original receipt time and authorized pause intervals; total elapsed time remains visible. Pauses do not silently extend a due date.
- Authorized rosters, explicit availability, conflict lists and actual appointment intervals; earliest-deadline/scarcity-aware proposal planning with explained unassigned cases.
- Transactional confirmation with ordered member locks and a database trigger that checks overlaps across institutions, regions and different committees. Proposed appointments are not reservations.
- EVC queue/readiness, scheduling deadline, confirmation, planned visit, actual completion, report submission and independent acceptance milestones. A pack explicitly selects the report-clock origin.
- Generation-checked Temporal deadline workflows, deduplicated in-app reminders/escalations, recipient-scoped alert visibility and acknowledgement without compliance closure.
- Scoped case/obligation views, six report families, JSON snapshots with hashes, CSV exports with formula-injection protection, and protected domain history plus receipts in the existing audit hash chain.
- Expiring regional, bureau, committee and competent-authority delegations. A supervisor cannot self-delegate or create a wildcard-region grant through the API. Delegated evidence delivery uses the existing audited delivery boundary.
- A responsive browser workspace at `/niyam`, backed by real APIs. It includes work queues, case details, compliance, EVC planning, process packs, alerts and reports.

## Important boundaries

This is a development prototype, not a production-qualified regulatory system. Its implementation does not validate the substance of an AICTE policy or authorize a real regulatory action.

The supplied `backend/fixtures/niyam_demo_pack.json` is **illustrative**. Its category mappings, elapsed-second targets, sources and templates are not official APH rules. In particular, its EoA mapping is a demonstration, not a universal prescription. Replace it only through source review, approved policy configuration and independent publication.

The current calendar engine uses explicitly labelled elapsed seconds. It does not implement official holiday/business-day calendars or ingest current amendments automatically. Obligation dates are explicit timezone-aware dates supplied with a source reference. Do not translate a business-day rule into elapsed seconds without an approved interpretation.

The planner is a baseline heuristic and does not claim global optimality. Offline travel feasibility, live committee-selection integration, large-scale optimization and CP-SAT are not implemented. The online/offline roster mode is recorded; an offline roster requires a responsible official to validate travel feasibility before recording availability.

New domain reminders/escalations are **in-app**. The existing email delivery foundation has not been wired to automatically email these new domain alerts. Running a deadline activity in a test verifies its persisted behavior; it does not establish a live Temporal-cluster soak test, real email delivery or legal service of notices.

The browser uses an existing bearer token for this developer prototype. The token stays in memory and is cleared on disconnect; this is not a completed SSO login experience. Use the configured OIDC issuer for a real deployment. Fixture MFA is explicitly simulated local assurance.

The initial UI exposes the primary workspaces and common review actions. Some configuration and less common lifecycle operations remain available through the authenticated API documentation rather than dedicated browser forms. No existing AICTE production API has been connected. No ML delay predictor, automatic legal interpretation, blanket Class-3 DSC verification or automatic adverse decision is claimed.

Standalone institution document watches can be created without a case. A response that uses the existing intake pipeline must reference a matching application/evidence slot. The prototype does not create arbitrary new document slots on an already frozen application. Model a suitable slot before submission or validate a separate intake design before expanding this behavior.

## Start the prototype

Use the existing platform instructions in `GETTING_STARTED.md`. Preserve the existing credentials and `.env`; do not paste a test database URL into production configuration.

With the project's normal development database configured:

```powershell
.\backend\.venv\Scripts\python.exe -m workbench.platform.migrate
```

The API and workers must use their existing separate runtime credentials. Restart the API, outbox relay and lifecycle worker after the upgrade. The lifecycle worker now registers `NiyamDeadlineWorkflow`, `load_niyam_deadline` and `fire_niyam_deadline`.

Open:

- `http://127.0.0.1:8000/niyam` for the workspace.
- `http://127.0.0.1:8000/docs` for authenticated API exploration.

Migrations `0019` through `0024` add the new domain, renewal permits, delegated evidence handoffs, indexed lookups and restricted draft-policy/roster visibility. They were exercised against a separate local PostgreSQL review database; the user's configured main database was not migrated by this implementation run. Do not use metadata `create_all` as a substitute for these RLS and integrity migrations.

## Local fixture roles

The existing seed includes these synthetic local subjects:

| Purpose | Subject |
| --- | --- |
| Institution A editor | `11111111-1111-4111-8111-111111111111` |
| Processing officer | `33333333-3333-4333-8333-333333333333` |
| Regional supervisor | `55555555-5555-4555-8555-555555555555` |
| Process-pack author | `77777777-7777-4777-8777-777777777777` |
| Process-pack approver | `88888888-8888-4888-8888-888888888888` |

In local fixture mode, generate the appropriate token with the existing tool, for example:

```powershell
.\backend\.venv\Scripts\python.exe -m workbench.tools token --subject 77777777-7777-4777-8777-777777777777 --mfa
```

Paste it into the workspace's Access token field. Use distinct author and approver identities. Fresh elevated actions expire after the configured MFA age. These subjects are not production accounts and the command refuses non-fixture authentication mode.

A processing officer still needs the appropriate assignment. Competent-authority status is never inferred merely from being a supervisor. Use a separately authorized, expiring delegation for a named application or region and record the authorizing source.

## Create a synthetic demonstration

After migrating and starting the normal local API, the following command exercises real authenticated API requests to create a demo process pack, independently publish it, submit a synthetic application, create an approval case, add an overdue renewal watch and record an authorized online roster:

```powershell
.\backend\.venv\Scripts\python.exe backend/tools/seed_niyam_demo.py --base-url http://127.0.0.1:8000
```

The script accepts only a loopback HTTP destination and a local/test fixture profile. It does not print tokens, change role assignments, connect to production AICTE systems or issue a regulatory decision. Each run creates a new set of synthetic records. Inspect the printed references and use the role-specific tokens described above to view or act on them.

## Prototype demonstration

1. As the author, create a process-pack draft from the fixture. As the independent approver, publish it with a review note.
2. Submit a synthetic intake application through the existing API. Its category and cycle must match the chosen demo pack. Keep an optional renewal evidence slot in that intake if the demonstration needs later uploads.
3. As a scoped processing officer/supervisor, create an approval case. Open its current stage, permitted actions, policy basis, clocks and history.
4. Record a reasoned return and demonstrate that a stale command fails. A replay with the same idempotency key returns the recorded result rather than moving twice.
5. Create an undertaking or validity watch. Grant a bounded upload permit if a post-submission renewal is needed. Complete the existing quarantine/scan process, then submit the clean evidence reference.
6. Show that the institution's upload leaves the old accepted expiry and review obligation unchanged. An authorized independent reviewer can verify or return the response.
7. For an EVC route, create a sourced roster and availability. Generate proposals, then confirm one. Conflicting member bookings fail even across different rosters.
8. The assigned committee records completion and a clean report. A different authorized officer accepts the report before the configured route can advance. The clock origin comes from the pinned pack.
9. Demonstrate an authorized final decision and verify that an unrelated continuing obligation remains open. Show alerts separately from fulfillment and compare the six scoped reports.

Do not advance the operating system clock for demonstrations. Use a controlled test clock or explicit illustrative past/future dates in the isolated test environment.

## API map

All mutation routes require an `Idempotency-Key` and a valid bearer token. Regulatory/governance operations additionally enforce fresh MFA and the relevant assignment/delegation.

| Capability | Endpoints |
| --- | --- |
| Session/workspace permissions | `GET /api/v1/niyam/session` |
| Policy drafting/publication | `GET/POST /api/v1/process-packs`; `POST /api/v1/process-packs/{id}/publish` |
| Scoped delegation | `POST /api/v1/niyam/access-grants`; `POST /api/v1/niyam/access-grants/{id}/revoke` |
| Approval cases | `GET/POST /api/v1/approval-cases` |
| Explanation and dossier | `GET /api/v1/approval-cases/{id}/next-actions`; `GET /api/v1/approval-cases/{id}/case-summary` |
| Guarded movement | `POST /api/v1/approval-cases/{id}/transitions` |
| Operational pauses | `POST /api/v1/approval-cases/{id}/pause` |
| Governed communication draft | `POST /api/v1/approval-cases/{id}/notice-drafts` |
| Continuing compliance | `GET/POST /api/v1/obligations` |
| Response permission/submission | `POST /api/v1/obligations/{id}/upload-permits`; `POST /api/v1/obligations/{id}/responses` |
| Official verification/extension | `POST /api/v1/obligations/{id}/reviews`; `POST /api/v1/obligations/{id}/extensions` |
| Authorized rosters | `GET/POST /api/v1/evc-rosters` |
| Appointment planning | `POST /api/v1/evc-plans`; `POST /api/v1/evc-appointments` |
| Confirmation and milestones | `POST /api/v1/evc-appointments/{id}/actions` |
| Dashboard | `GET /api/v1/analytics/pendency-dashboard` |
| Reports | `GET /api/v1/reports/consolidated?report_type=...&format=json` or `format=csv` |
| In-app follow-up | `GET /api/v1/niyam/alerts`; `POST /api/v1/niyam/alerts/{id}/acknowledge` |

Report types are `PENDENCY`, `EVC_STATUS`, `UNDERTAKING_COMPLIANCE`, `DOCUMENT_VALIDITY`, `OVERDUE` and `REGIONAL_PERFORMANCE`.

Appointment actions are `CONFIRM`, `CANCEL`, `COMPLETE`, `SUBMIT_REPORT` and `ACCEPT_REPORT`. Cancelling an unconfirmed alternative does not erase an already confirmed appointment's milestones.

## Verification and research

The complete regression run passed **199 tests**, with **17 skipped** external-service checks. These skips must not be represented as verified live-file, scanning or chaos coverage. The final targeted runs passed **17 NiyamFlow acceptance tests** (16 together, then the final region-visibility regression). See [verification results](NIYAMFLOW_VERIFICATION.md) for the exact scope.

The full regression uncovered and fixed an outbox recovery issue: unleased messages were filling the reconciliation batch before expired leases could be released. Reconciliation now selects expired owned leases, orders them deterministically and uses row locks with `SKIP LOCKED`.

Research and policy references remain in `output/SIH26262_FULL_REVISED_SOLUTION_AND_CHANGES.md`. Relevant primary references include the [official statement](https://www.sih.gov.in/sih2026PS), [AICTE handbook](https://www.aicte.gov.in/sites/default/files/APH%20Final.pdf), [OR-Tools solver documentation](https://developers.google.com/optimization/cp/cp_solver) and [NIST AI RMF](https://nvlpubs.nist.gov/nistpubs/ai/NIST.AI.100-1.pdf). These support design choices and boundaries, not performance claims for this prototype.
