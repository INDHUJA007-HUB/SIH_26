# SIH 2026 — AICTE Evidence and Compliance Workbench

This repository contains the consolidated research and solution specification for **AICTE PS26261**, focused on evidence-led application validation, document authentication, regulatory compliance, rectification, auditability, and officer review.

## Start here

- [Backend implementation plan](docs/BACKEND_IMPLEMENTATION_PLAN.md) — complete architecture and phased delivery specification.
- [Development setup](docs/development/GETTING_STARTED.md) — start and verify the backend and local stack.
- [Phase 2–4 implementation](docs/development/PHASE_2_4_IMPLEMENTATION.md) — persisted permissions, immutable submissions, quarantine scanning, delivery and operating procedures.
- [Phase 2–4 verification](docs/development/PHASE_2_4_VERIFICATION.md) — executed acceptance checks and remaining deployment gates.
- [Intake API example](docs/api/intake-example.md) — draft → upload → scan → submit → inspect history.
- [Phase 0 baseline](docs/phase-0/README.md) — requirements, architecture decisions, policy issues, threat model, backlog and evaluation plan.
- [Phase 0–1 verification](docs/development/PHASE_0_1_VERIFICATION.md) — executed checks, evidence and remaining external gates.
- [`output/AICTE_PS26261_Revised_Solution_Context.pdf`](output/AICTE_PS26261_Revised_Solution_Context.pdf) — formatted 28-page research report.
- [`output/AICTE_PS26261_Revised_Solution_Context.md`](output/AICTE_PS26261_Revised_Solution_Context.md) — editable report source.
- [`output/AICTE_PS26261_Source_Register.json`](output/AICTE_PS26261_Source_Register.json) — source URLs, provenance, retrieval details, pinned competitor revisions, and hashes.
- [`output/AICTE_PS26261_Rule_Evidence_Register.json`](output/AICTE_PS26261_Rule_Evidence_Register.json) — draft, evidence-linked rule records. Every rule remains disabled for production and adverse action until it passes legal/policy approval and testing.

## Repository structure

```text
backend/   FastAPI application, persisted identity/intake domain, migrations, workers and tests
infra/     Digest-pinned local platform and non-root backend container
scripts/   Repeatable Windows and Unix bootstrap/start/check/stop
docs/      Implementation plan, baseline decisions and developer/operator guides
benchmarks/ Evaluation manifest schema; no real applicant data
output/    Final report and machine-readable evidence registers
sources/   Uploaded source material and amendment copies used in the analysis
research/  Extracted text, pinned competitor evidence, QA records, and report builder
```

## Run the complete local platform

The root [`Dockerfile`](Dockerfile) builds two non-root targets: the backend API/workers and the network-isolated evidence parser. The Compose environment adds PostgreSQL, Temporal, development object storage, Keycloak, ClamAV, Mailpit and observability services.

Build from source with Docker plus Python/uv:

```powershell
.\scripts\dev.ps1 up
.\scripts\dev.ps1 check
```

Or use the published images with Docker only after cloning the repository:

```powershell
.\scripts\container.ps1 up
.\scripts\container.ps1 check
```

Linux/macOS users can run `sh scripts/container.sh up`. The API documentation is available at <http://127.0.0.1:8000/docs>. The first startup generates local-only credentials and fixture keys in ignored files. See the [complete container guide](docs/development/GETTING_STARTED.md#docker-only-published-images) before using custom tags or sharing access.

Temporary rendered page images used only for visual QA are intentionally excluded.

## Run the full test suite

Execute all 135 tests with zero skips across Phases 1 through 11:

```powershell
# PowerShell
$env:WB_INTEGRATION_DATABASE_URL = "postgresql+psycopg://workbench:<password>@127.0.0.1:5433/workbench"
$env:WB_FILE_INTEGRATION = "1"
$env:WB_CHAOS_INTEGRATION = "1"
uv run --project backend pytest backend/tests -q -rs
```

```bash
# Bash / Linux / macOS
export WB_INTEGRATION_DATABASE_URL="postgresql+psycopg://workbench:<password>@127.0.0.1:5433/workbench"
export WB_FILE_INTEGRATION="1"
export WB_CHAOS_INTEGRATION="1"
uv run --project backend pytest backend/tests -q -rs
```

### Required Environment Variables

- `WB_INTEGRATION_DATABASE_URL`: Connection string to migrated PostgreSQL on port 5433.
- `WB_FILE_INTEGRATION=1`: Activates live ClamAV file scanning, networkless PDF parsing, and S3 upload sessions.
- `WB_CHAOS_INTEGRATION=1`: Activates local parser fail-closed outage probes and outbox relay outage recovery tests.

To run static type checking:
```powershell
uv run --project backend mypy --config-file backend/pyproject.toml backend/src/workbench
```

## Evidence labels

The report distinguishes claims by provenance:

- **V-U** — verified against an uploaded source.
- **V-P** — verified against a primary web source.
- **V-M** — verified against a public mirror where the publisher copy was unavailable.
- **C-S** — verified by inspecting pinned competitor source code.
- **C-R** — competitor author/README claim, not independently demonstrated.
- **P** — proposed design, target, or implementation plan.
- **O** — open question requiring authoritative confirmation.

These labels are important: proposed product behavior and benchmark targets must not be presented as completed or independently validated capabilities.

## Important compliance caveats

- AICTE's official website and some approval routes were unavailable during the final verification pass. Current-year completeness therefore remains unresolved where only mirrored amendment copies were accessible.
- The Annexure 4 faculty-cadre formulas contain an arithmetic/interpretation ambiguity documented in the report. They must not be converted into adverse automated findings without an approved interpretation.
- Source authentication, completeness, forensic concern, document validity, and regulatory compliance are modeled as separate decisions. A forensic signal alone is not proof of fraud or non-compliance.
- The sample rule register is a design artifact, not a production policy pack. It requires maker-checker approval, version pinning, regression tests, and legal/policy sign-off.
- Third-party competitor snapshots under `research/` are retained solely as pinned research evidence. Their original repositories and licenses govern reuse.

## Research scope

The package covers:

- AICTE Approval Process Handbook 2024–27 and accessible 2025–26/2026–27 amendments.
- Correction of earlier assumptions around faculty ratios, cadre formulas, safety certificates, video evidence, rectification, and affidavit requirements.
- The seven requested additions: video checks, alert workflows, applicant/officer reports, access logging, audit/pending-action screens, a visible discrepancy check, and separated completeness/source/forensic outcomes.
- Competitive implementation review with revision-pinned evidence.
- Architecture, data model, APIs, rule governance, security, privacy, retention, accessibility, and licensing considerations.
- Prioritized build plan, five-minute demo narrative, evaluation design, red-team tests, and claim-readiness register.

## Reproducibility

Input SHA-256 hashes and web-source metadata are stored in the source register. The report builder is in `research/build_deliverables.py`; its environment-specific font/runtime assumptions may need adjustment on another machine.

## Research date

The final verification pass was completed on **26 October 2026**. Revalidate AICTE circulars, amendments, portal behavior, data-protection commencement dates, and integration availability before a production deployment or formal compliance claim.
