# Phase 0–1 implementation and verification

Verified on 26 October 2026 in `C:\SideQuest\SIH`. This is the active repository directory for this implementation. Research/source material from the existing GitHub repository is preserved. Changes in this delivery are local working-tree changes; no new GitHub push or remote workflow run is claimed.

## Delivered phase scope

| Subphase | Delivered implementation/artifacts | Outcome |
| --- | --- | --- |
| 0.1 Requirements and claims | 34 numbered requirements, seven-addition mapping, capability/claim register, synthetic pilot scope and 20 acceptance scenarios | Complete engineering baseline |
| 0.2 Policy/process baseline | All 22 research records imported as disabled drafts; issue register, scoped synthetic process template, selected demonstration scenarios and publication checklist | Complete development baseline; regulatory sign-offs remain external gates |
| 0.3 Architecture and compatibility | 12 ADRs, context/trust/deployment design, data classes/threat model, actual PDF/font/signature/OCR/Temporal/S3 compatibility probes | Complete for the declared prototype scope |
| 0.4 Delivery and quality | Dependency-ordered backlog/milestones, role ownership, test strategy, benchmark schema, budget model and onboarding tracker | Complete; people/provider/budget approvals are not fabricated |
| 1.1 Backend foundation | Runnable typed FastAPI app, configuration/error contracts, module ports/boundaries, health/build/capabilities and authenticated synthetic use case | Implemented and tested |
| 1.2 Local platform | Windows/Unix setup, pinned Compose images, PostgreSQL migration/idempotent seed, three S3 buckets, Temporal worker/queue, Keycloak identities, Mailpit, monitoring stack | Actual complete local stack started and smoke-tested |
| 1.3 CI/supply chain | Ubuntu/Windows quality workflow, PostgreSQL/Compose jobs, dependency/secret/image scanning, SBOM, gated signed/provenance release and OIDC identity workflow, review/exception policy | Implemented; local gates passed; remote CI/sign/release not executed |
| 1.4 Observability | Structured allowlist logs, request correlation/trace propagation, SQL sanitization, workflow/activity logging/tracing, OTLP collector, Prometheus and Grafana/Jaeger | Actual metrics/dashboard/request and worker traces verified |

## Executed results

| Check | Observed result |
| --- | --- |
| Python tests, including PostgreSQL integration | **22 passed, 0 failed, 0 errors, 0 skipped** |
| Ruff lint and formatting | Passed for source, tests, tools and migrations |
| Strict mypy | Passed for all 39 source files |
| Module import boundaries | Passed |
| Repository contracts | 12 ADRs; 22 disabled research drafts; pinned action/image references; loopback port policy passed |
| High-risk credential-format scan | Passed; values never printed |
| Database migration | Upgrade head and schema-drift check passed against actual PostgreSQL |
| Repeatable synthetic seed | Two institutions and 22 disabled draft candidates; repeated seeding succeeded |
| HTTP API fixture | Health 200; unauthenticated request 401; authenticated own synthetic institution 200 |
| Identity verification | Actual local Keycloak token issuer/audience/signature and server-side subject assignment passed |
| S3-compatible simulator | Three versioned buckets; reused upload grant and preserved earlier object version verified |
| Temporal | Actual worker executed the foundation workflow and returned `SYNTHETIC_PLATFORM_OK` |
| Monitoring | Mailpit and Grafana health, provisioned dashboard, Prometheus API scrape, collector-to-Jaeger traces passed |
| Trace services | `workbench-api` and `workbench-worker` present in Jaeger |
| PDF/font/signature spike | Text extraction, word geometry, font render and synthetic signature integrity passed |
| OCR spike | Actual PaddleOCR CPU inference found the expected token in one synthetic English image |
| Python environment audit | No known vulnerabilities reported after updating Pillow to 13.0.0 |
| Backend runtime image audit | Trivy HIGH/CRITICAL gate: **0 findings** for the tested image |
| SBOM | CycloneDX JSON generated for selected Python environment |
| Documented commands | `scripts/dev.ps1 up` and `scripts/dev.ps1 check` both completed successfully |

The scan is a dated finding for the scanned environment/image, not a guarantee of future vulnerability absence or coverage of every development sidecar. Re-run scans on dependency/image changes. Sidecars are loopback-exposed development services, not approved production deployment artifacts.

## Selected compatibility versions

Native Python: 3.12.13. API container Python: 3.12.15. FastAPI 0.162.0; Pydantic 2.14.1; SQLAlchemy 2.1.6; Temporal SDK 1.34.0; pypdf 6.21.2; pdfplumber 0.11.10; pypdfium2 5.14.0; ReportLab 4.5.1; pyHanko 0.38.0; cryptography 50.0.2; Pillow 13.0.0. Full resolved dependency versions/hashes are in `backend/uv.lock`.

OCR is isolated: PaddleOCR 3.7.0 / PaddlePaddle 3.3.1, `PP-OCRv5_mobile_det` and `en_PP-OCRv5_mobile_rec`. Windows CPU dependency hashes are in `backend/spikes/ocr-requirements.txt`; actual model-file hashes are recorded by the probe. This proves one-image compatibility, not application accuracy or Indian-language support.

API image uses a digest-pinned Python builder and non-root distroless Debian 13 runtime. Only the required Python/shared libraries and application environment enter runtime; package managers/build tools and unused operating-system utilities are excluded. Native imports, migrations, HTTP request and worker execution passed in that runtime. The API receives only the fixture directory JSON and public verification key, not the signing private key. Worker/migration containers receive no fixture private-key mount.

Docker Desktop 4.96.3 was installed with the user's explicit approval. Docker engine 29.9.2 and Compose 5.6.1 were used. Project-local uv 0.13.4 is available under ignored `.tools/uv/`; CI and image builds pin this patched version. The existing system uv installation was not overwritten. The PowerShell launcher prefers the project-local binary.

## Evidence and reproduction

Generated artifacts are intentionally ignored by Git: `artifacts/verification.json`, `artifacts/tests.xml`, `artifacts/platform-smoke.json`, `artifacts/dependency-audit.json`, `artifacts/image-audit.json`, `artifacts/sbom.cdx.json`, and `artifacts/spikes/`. Local keys/credentials are in ignored `.local/` and `.env` and must not be published.

```powershell
.\scripts\dev.ps1 up
.\scripts\dev.ps1 check
.\.tools\uv\bin\uv.exe run --project backend python backend/tools/verify_foundation.py --integration
```

On a fresh clone without the project-local tool cache, install the documented uv version and use the equivalent `uv run` command. The bootstrap never silently resets existing credentials or database volumes. The local stack is left running for inspection; `scripts/dev.ps1 stop` stops its containers without removing named volumes.

## Explicit later-phase/external gates

- No production rules or adverse machine actions are enabled. A real policy owner must resolve currency/interpretation and approve the actual release/process policy.
- Human names for regulatory approval, data ownership, production budget and source onboarding are organizational assignments, not invented sign-offs in this code delivery.
- Full Phase 2 case assignments, RLS, privileged roles and production identity/session controls remain to be implemented. The synthetic fixture endpoint is not a complete authorization system.
- Live AICTE/DigiLocker/EntityLocker/state-source access requires actual authorization/contracts; none is claimed.
- GitHub branch protection, required reviewers, cloud role trust, environment approvals, remote CI, signed publication and deployment need repository/account configuration and execution. Workflows are provided and guarded; no cloud resources were created.
- Model quality, representative packet evaluation, regional-language claims, independent security assessment and production recovery are later qualification gates.

These boundaries are enforced or disclosed rather than hidden behind a “production ready” label.
