# Phase 2–4 implementation verification

Verified on **27 October 2026** in `C:\SideQuest\SIH`. This is a working local synthetic development release. The [implementation and operating procedures](PHASE_2_4_IMPLEMENTATION.md), [complete plan](../BACKEND_IMPLEMENTATION_PLAN.md), [OpenAPI contract](../api/openapi.json), and [machine-readable evidence](phase-2-4-evidence.json) accompany this record.

## Executed results

| Check | Actual result |
|---|---|
| Complete native + PostgreSQL + S3 + Temporal + ClamAV + parser suite | **65 passed, 0 failed, 0 skipped**, 193.11 seconds |
| Real service outage probes | Parser timeout stayed quarantined and recovered; committed outbox survived unavailable Temporal and repeated delivery finalized one receipt/task |
| Ruff lint and formatting | Passed |
| Strict mypy | Passed across 66 source files |
| Module architecture, repository configuration and credential-format checks | Passed |
| Alembic forward migration and schema drift check | Head `0006_scope_guards`; no new upgrade operations |
| Runtime database authority | All five service logins non-superuser/non-bypass/non-role-admin; API and workers validate their assigned group |
| Protected object tables | Nine inspected application/evidence/history/task relations enforce and force RLS |
| Actual parser isolation | Network `none`, UID/GID `65532:65532`, read-only root, all capabilities dropped, 1 GiB container memory and 64-PID ceiling |
| Live local OIDC | Keycloak JWKS/access-token validation and persisted membership passed |
| Foundation platform smoke | Authenticated fixture, idempotent seeds, versioned storage, Temporal, mail sink, metrics, provisioned dashboard and collector-to-Jaeger traces passed |
| Intake observability | API, relay, scan and reconciliation Prometheus targets all UP |
| Dependency audit | 130 packages; no known vulnerabilities reported |
| Runtime and parser image scans | Both passed Trivy HIGH/CRITICAL gate with **0 findings** at verification time |
| Deployed code correspondence | All 66 Python source files in the running API image matched the working source byte-for-byte |
| Real API-backed demonstration | Created, uploaded, scanned, accepted and submitted one explicitly synthetic packet; frozen summary has one selected accepted version and no missing slot |

The suite reports two dependency deprecation warnings: Starlette's current httpx test-client compatibility path and the pypdf JavaScript-fixture helper. Neither was suppressed. They do not indicate a failed test. Coverage XML is retained; worker execution inside Docker is exercised by acceptance tests but is not attributed to native Python coverage.

## Subphase completion and concrete evidence

| Subphase | Implemented deliverable | Verification |
|---|---|---|
| 2.1 | Issuer/audience/RS256 validation, persisted subject mapping, recent MFA policy, expiry/session/identity revocation, `/me` | Live Keycloak contract plus malformed assurance, disabled identity, expired assurance, revoked token and forged role-claim tests |
| 2.2 | Central scope/action kernel, property restrictions, permission catalogue, safe error contracts | Own/foreign/unassigned case tests; extra-property tampering; editor versus auditor/emergency write denial; original/preview/range/history isolation |
| 2.3 | Non-owner service roles, forced RLS, transaction-local context and composite ownership constraints | Runtime role inspection, owner-credential rejection, no-context/alternating-tenant connection tests, foreign slot/link denial and reviewed forward SQL |
| 2.4 | Scoped assignment grant/revoke/expiry, membership administration, account disable, bounded read-only emergency access | Fresh-MFA/jurisdiction checks; assignment and membership revocation; independent-person role separation; emergency approval/read-only/revocation tests |
| 3.1 | Persisted scoped drafts/revisions/declarations, normalized portal references, idempotency | Duplicate normalized imports; changed-content key conflicts; concurrent revisions and expected-revision failures |
| 3.2 | Versioned slots/evidence, canonical immutable manifests and submitted guards | Exact clean/quarantine version tests; replayed submission; concurrent submit finalizes once; immutable SQL history and post-submit edit denial |
| 3.3 | Atomic audit/outbox/receipt transactions, hash-chain verifier, leased relay and lag metrics | Injected outbox write rolls back revision/state/audit; hash chain verifies; real relay outage/unavailable Temporal and duplicate-workflow delivery recover with one finalized receipt/task |
| 3.4 | Bounded list/revision/evidence/audit/access histories, stored summaries, indexes and API contracts | Counts reconcile with selected manifest; query plans captured; generated OpenAPI and real demo summary retained |
| 4.1 | Single/multipart quarantine grants, expiry/abort, scoped reservations, size/type/checksum checks and version pins | Actor/storage/processing limits; foreign slot; expired/aborted session; missing/wrong-sized/extra-index multipart parts; one- and two-part success; reused grant and changed latest object |
| 4.2 | Actual malware worker, signature freshness, bounded networkless inspection, fail-closed promotion and transient cleanup | Benign PNG/multipage PDF/MP4; MIME spoof, malformed/encrypted/active-content PDF, page limit, EICAR and wrong checksum; actual parser outage and recovery |
| 4.3 | Authorized GET/HEAD originals, PNG pages, range validation, safe headers and durable start/end access records | Full/partial/HEAD delivery; invalid/multiple/foreign ranges; preview isolation; quarantine denial; completion bytes and abort before first byte |
| 4.4 | Bounded cursor reconciliation, missing/stuck/orphan tasks and operational metrics/runbooks | Missing preview produces a stored task while the accepted original remains available; version-specific checks, deduplication, non-destructive inventory and metric scrape verification |

This matrix describes implemented local capabilities. It does not claim real-cloud or regulatory qualification.

## Reproduce the checks

Start Docker Desktop, then run from the repository:

```powershell
.\scripts\dev.ps1 up
.\.tools\uv\bin\uv.exe run --project backend python backend/tools/run_intake_tests.py --failure-probes --cov=workbench --cov-report=xml --junitxml=artifacts/phase-2-4-tests.xml
.\.tools\uv\bin\uv.exe run --project backend python backend/tools/check_intake_platform.py
.\.tools\uv\bin\uv.exe run --project backend python backend/tools/check_oidc.py
```

If uv is installed on PATH, use `uv` instead of the project-local executable. Linux/macOS uses `sh scripts/dev.sh up` followed by the same uv commands. `run_intake_tests.py` loads the local URL directly into the test process without printing credentials. The failure probes temporarily stop **only this project's parser and relay** and restore them in `finally` blocks. Use a disposable development stack.

For an additional real local demonstration:

```powershell
.\.tools\uv\bin\uv.exe run --project backend python backend/tools/intake_demo.py
```

That command creates another clearly labelled synthetic case; it does not reset or replace existing records. The already executed demo is application `08dc0361-1bd7-4155-ac83-cd9961854892`, submitted revision 2, manifest SHA-256 `9c4e7b0ae2ca23049d0bc3a68901b0ffc5527b11d140662716ce04b5165f44e0`. It belongs to the seeded institution A and can be read using the local fixture or Keycloak institution A identity. Evidence `ae349cdc-79de-4168-ba20-3c44d5794783` has an accepted original and a PNG preview. Its summary explicitly returns `NOT_IMPLEMENTED_UNTIL_PHASE_8` for source verification and `NOT_EVALUATED` for compliance.

## Evidence and operating boundaries

Raw local results live in `artifacts/phase-2-4-tests.xml`, `backend/coverage.xml`, `artifacts/intake-platform.json`, `artifacts/intake-demo.json`, the dependency audit and the two image audit JSON files. Query plans are included in the platform artifact. These generated files are intentionally ignored by Git; the concise checked evidence JSON is versionable. CI is configured to execute native, PostgreSQL and Compose checks and scan both image targets. No GitHub Actions execution, protected-branch configuration, image publication or cloud rollout is claimed by this local run.

Package downloads in this Windows Docker environment needed a verified cache warm-up and build-network troubleshooting. The final build uses locked wheel origins, size/SHA verification and offline required-hash installation. Both images were rebuilt and their deployed Python source compared to the working tree. The normal source/configuration, identity, mutation and file checks all passed after the rebuild.

The development S3 emulator is disposable across container replacement. Deliberately missing objects and other synthetic failure fixtures can leave operations tasks in the test institutions; those tasks are evidence of injected faults. Accepted evidence is never automatically deleted by the reconciler. Keep a real storage/metadata backup and restore design for deployment.

## Remaining external and later-phase work

- Cloud IdP enrollment, organization-approved identity/person mapping and real MFA assertion qualification need the selected organization's deployment. The live local Keycloak contract and simulated privileged-assurance tests are distinct results.
- AWS IAM/KMS/Object Lock, private network controls, cloud checksum/signature behavior, backup/restore and production capacity qualification are deployment gates. The storage policy is a reference template, not a deployed account policy.
- The local parser is a restricted shared development service with one bounded child at a time. Per-job task/container isolation under a hostile parser compromise, independent security review and production workload qualification remain deployment/security acceptance requirements; network isolation alone is not a complete adversarial security proof.
- Complete processing-job operations are Phase 5. Extraction/OCR, normative rules, live issuer/AICTE integration, report generation, rectification, alerts and semantic video checks belong to subsequent phases. Regulatory production rules remain disabled, and no official decision or authenticity claim is made.

Vulnerability results describe the scanners' known findings on the recorded versions and date. They are not a guarantee that native parser libraries or all future threats are vulnerability-free.
