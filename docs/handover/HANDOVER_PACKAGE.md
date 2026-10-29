# Handover Package & Service Transition Index

**Document Reference:** `docs/handover/HANDOVER_PACKAGE.md`  
**Target Specification:** `docs/BACKEND_IMPLEMENTATION_PLAN.md` Section 15.2 & Section 10 (Phase 15.4)  
**Status:** COMPLETE / PHASE 15 PRODUCTION PILOT TRANSITION  
**Classification:** Confidential — System Engineering & Governance  
**Publication Date:** October 2026  

---

## Executive Summary

This Handover Package provides the comprehensive operational index, architectural ledger, regulatory provenance matrix, and quality qualification record for the **AICTE Evidence Workbench Backend**. The platform transitions from implementation across Phases 0–15 to operational pilot readiness, adhering strictly to:
1. **Honest Pilot Boundaries:** Advisory-only machine evaluations, frozen canonical ground truths, immutable audit checkpoints, and zero fabricated live integrations.
2. **Deterministic Governance:** Independent two-party rule approval, bitemporal institutional record matching, non-destructive migrations, and automated access sweeps.
3. **Data Protection & Legal Assurance:** Tiered data-class retention (CERT-In 180-day security log minimum, 7-year audit minimum), non-bypassable legal holds, and cryptographic purge manifests.

---

## 1. Architecture

| Artefact Category | Location / Reference | Description & Key Responsibilities |
| :--- | :--- | :--- |
| **System Context & Topology** | `docs/BACKEND_IMPLEMENTATION_PLAN.md` §3.1–3.3 | Multi-tier trust boundary model separating Public Edge, Application Zone, Isolated Untrusted Processing, Connector Zone, Control Zone, and Audit/Recovery Zone. |
| **Runtime Deployment Units** | `docs/BACKEND_IMPLEMENTATION_PLAN.md` §3.2 | 11 dedicated deployment units: `api`, `evidence-delivery`, `outbox-relay`, `workflow-worker`, `scan-worker`, `document-worker`, `connector-worker`, `evaluation-worker`, `media-worker`, `report-worker`, `audit-worker`. |
| **Architecture Decision Records (ADRs)** | `docs/architecture/adr/` | Immutable records covering: Temporal durable workflows (ADR-001), PostgreSQL RLS (ADR-002), S3 Object Lock & Encryption (ADR-003), Rule DSL compilation (ADR-004), and Dual-database operational isolation (ADR-005). |
| **Module Domain Responsibilities** | `backend/src/workbench/modules/` | 19 fully implemented modules adhering to 4-tier DDD layering (Domain, Application, Infrastructure, Interface). Zero README-only stubs remain. |
| **Dependency Inventory & SBOM** | `backend/pyproject.toml`, `backend/uv.lock` | Reproducible lockfile with pinned versions: Python 3.12, FastAPI, SQLAlchemy 2, Alembic, Temporal Python SDK, OpenCV, Pillow, pypdfium2. |

---

## 2. API & Integration Contracts

| Artefact Category | Location / Reference | Description & Key Responsibilities |
| :--- | :--- | :--- |
| **REST API Router Tree** | `backend/src/workbench/api/` | Routers for Foundation, Intake, Verification, Review & Rectification, Tasks/Alerts/Audit, Media/Spatial, Rule Governance, Retention, Operations. |
| **OpenAPI Specification** | `GET /openapi.json` | Auto-generated typed OpenAPI v3.1 schema covering all endpoints, parameters, and error responses. |
| **Error Handling Catalogue** | `backend/src/workbench/platform/errors.py` | Structured application errors conforming to RFC 7807 (`ApplicationError`, `AccessDenied`, `NotFoundError`, `AuthenticationRequired`). |
| **Transactional Outbox Events** | `backend/src/workbench/platform/outbox.py`, `tables.py` | Transactionally published domain events (`EvidenceSubmitted`, `EvaluationCompleted`, `RectificationRequested`, `RetentionPurgeCompleted`). |
| **Provider Capability Matrix** | `backend/src/workbench/modules/verification/simulator.py` | Typed simulator registry tracking AICTE historical, Fire Safety, and Land Records status (`SIMULATED`, `live_coverage_available=False`). Live government connectors (AISHE, MCA21, RoC) are not implemented in verification code; production connector is blocked by missing access. |

---

## 3. Data Architecture & Invariants

| Artefact Category | Location / Reference | Description & Key Responsibilities |
| :--- | :--- | :--- |
| **Schema & Table Definitions** | `backend/src/workbench/adapters/tables.py` | Complete SQLAlchemy metadata defining 38 tables, composite unique keys, foreign keys, and indexes. |
| **Alembic Migrations** | `backend/migrations/versions/` (0001–0016) | Strictly forward-compatible, reviewed migrations: `0001_initial` through `0016_phase_15_ops_retention`. Expand-contract compatibility verified by `verify_migrations.py`. |
| **Multi-Tenancy & RLS** | `docs/data/tenant_policies.sql`, `wb.can_access()` | PostgreSQL Row-Level Security policies enforcing cross-tenant institutional isolation, case reviewer scoping, and session reset. |
| **Retention & Legal Holds** | `backend/src/workbench/modules/retention/` | Versioned data-class retention policies (`ORIGINAL_EVIDENCE`, `DERIVATIVES_CACHES`, `REPORTS`, `AUDIT_CHECKPOINTS`, `CERT_IN_SECURITY_LOGS`). Non-bypassable legal holds. Cryptographic `PurgeManifest` with SHA-256 digest. |
| **Canonical Fact Storage** | `backend/src/workbench/modules/claims/` | SHA-256 fingerprinting of normalized facts, immutable member links, bitemporal observation tracking. |

---

## 4. Regulatory Policy & Rule Engine

| Artefact Category | Location / Reference | Description & Key Responsibilities |
| :--- | :--- | :--- |
| **Regulatory Source Register** | `docs/policy/SOURCE_REGISTER.md` | Authoritative register of AICTE Approval Process Handbook clauses, Gazette notifications, and circular locators. |
| **Golden Rule Vectors** | `benchmarks/fixtures/golden_vectors.json` | 22 comprehensive test vectors validating land area, faculty cadre ratio, built-up space, bandwidth, and student intake. |
| **Two-Party Rule Approval** | `backend/src/workbench/modules/rule_governance/` | Author and approver role separation. Candidate impact simulation producing finding diffs against frozen test sets before publication. |
| **Release Manifests** | `backend/src/workbench/modules/rule_registry/` | Immutable `RuleRelease` bundles pinned by cryptographic release hash. Zero in-place mutation of historical releases. |
| **Emergency Rollback Procedure** | `docs/runbooks/RUNBOOK_RULE_ROLLBACK.md` | Re-publishing approved prior release with signed justification and lineage retention. |

---

## 5. Evidence Processing, Media & AI

| Artefact Category | Location / Reference | Description & Key Responsibilities |
| :--- | :--- | :--- |
| **Document Classification & OCR** | `backend/src/workbench/modules/extraction/` | Layout/text classification with `UNKNOWN_DOCUMENT_TYPE` fallback. PaddleOCR/Tesseract interface pinning coordinate geometry. |
| **Bounded Media Inspection** | `backend/src/workbench/modules/media_analysis/` | Video duration checks, bounded frame sampling (1 frame / 10s, max 180 frames), pHash/dHash near-duplicate detection. |
| **Equipment Verification** | `backend/src/workbench/modules/media_analysis/` | Advisory bounding-box counting for visible workstations. Explicit uncertainty intervals; never asserts fraud on partial occlusion. |
| **Model & Template Drift Engine** | `backend/src/workbench/modules/operations/drift.py` | Champion/challenger extraction evaluation over frozen benchmark packets (`packet_manifests.json`). Read-only; zero mutation of historical runs. |
| **Benchmark Manifests** | `benchmarks/manifests/packet_manifests.json` | Frozen synthetic benchmark packets (digital, scanned, deficient bandwidth, cadre ambiguity, fraud twins). |

---

## 6. Quality & Qualification Results

| Artefact Category | Location / Reference | Description & Key Responsibilities |
| :--- | :--- | :--- |
| **Eight-Metric Qualification Report** | `benchmarks/evaluation/runner.py` | Measured accuracy across benchmark fixtures: Digital Extraction (97.5%), Scanned Extraction (91.4%), Validation Accuracy (100.0%), Anomaly Recall (100.0%), Discrepancy Reliability (100.0%), p95 Latency (1.39s / 10 pages). Category 4 explicitly records 0% live source resolution (all simulated). Category 8 is explicitly labeled STUDY_PENDING_UNMEASURED (no human trial conducted; hypothesized 30% reduction is unmeasured). |
| **Comprehensive Test Suite** | `backend/tests/` | Unit, property (Hypothesis), integration, contract, security, workflow replay, and acceptance tests covering Phases 0–15. |
| **Static Verification Checks** | `backend/tools/check_infra.py`, `check_runbooks.py` | Automated CI checks validating Terraform configuration and operational runbooks. |
| **Residual Risk Register** | `docs/security/RESIDUAL_RISKS.md` | Formally acknowledged pilot limitations (simulated provider mode, advisory machine findings, manual fallback requirements). |

---

## 7. Infrastructure, Operations & Runbooks

| Artefact Category | Location / Reference | Description & Key Responsibilities |
| :--- | :--- | :--- |
| **Terraform Configurations** | `infra/terraform/` | Modular IaC: VPC networking, ECS Fargate, Multi-AZ RDS PostgreSQL, Private S3 Buckets with Object Lock, KMS keys, Cognito OIDC. |
| **16 Operational Runbooks** | `docs/runbooks/` | Executable procedures covering: Source Outages, Stuck Workflows, Unsafe Files, Failed Reports, Suspected Cross-Tenant Exposure, Key Rotation, Rule Rollback, Outbox Backlog, Checkpoint Gap, Storage Mismatch, Database Restore, Regional Recovery, Legal Holds, Deployment Rollback, Provider Activation. |
| **Canary & Rollback Rehearsal** | `backend/tools/rehearse_rollback.py` | Automated drill proving safe forward and backward version deployment without schema corruption. |
| **Signed Release Manifest** | `backend/tools/release_manifest.py`, `docs/release/` | Cryptographically signed release manifest binding Git commit, Docker digests, migration heads, and test checksums. |
| **Health & Incident Containment** | `backend/src/workbench/modules/operations/` | Real-time SLO health aggregation, safe operator reconciliation, and incident containment isolating compromised actors/providers WITHOUT mutating compliance findings. |

---

## 8. Product & Demonstration Pack

| Artefact Category | Location / Reference | Description & Key Responsibilities |
| :--- | :--- | :--- |
| **5-Minute Narrative Walkthrough** | `docs/BACKEND_IMPLEMENTATION_PLAN.md` §14.1 | Step-by-step demonstration: Submit -> Source Outage -> Numeric Calculation -> Media Evidence -> Officer Rectification -> Governed Rule Update -> Immutable Audit Timeline. |
| **Synthetic Seed Fixtures** | `backend/src/workbench/adapters/fixtures.py`, `benchmarks/fixtures/` | Reproducible synthetic institution packets, certificates, and ground truth files. |
| **Seven Additions Acceptance Matrix** | `docs/BACKEND_IMPLEMENTATION_PLAN.md` §14.2 | 100% verified implementation of all 7 core architectural additions across Phases 1–15. |
| **Capability Register Endpoint** | `GET /api/v1/capabilities` | Server-enforced capability declaration revealing pilot scope, provider modes, and advisory-only machine evaluations. |

---

## 9. Governance, Access & Pilot Sign-Off

| Artefact Category | Location / Reference | Description & Key Responsibilities |
| :--- | :--- | :--- |
| **Named Role Accountabilities** | `docs/BACKEND_IMPLEMENTATION_PLAN.md` §13.3 | Explicit responsibilities defined for Technical Lead, Platform Engineer, Policy Approver, Document/ML Engineer, and Security Reviewer. |
| **Automated Access Sweeps** | `POST /api/v1/operations/access-review/sweep` | Automated sweep command revoking expired case assignments and stale memberships. |
| **Pilot Go/No-Go Decision** | `docs/policy/PILOT_GO_NO_GO.md` | Formal sign-off record verifying 10 required operational criteria prior to cohort expansion. |
| **Official Decision Boundaries** | `docs/policy/DECISION_BOUNDARIES.md` | Hard barrier: Workbench produces advisory findings and compliance reports; final statutory determinations reside exclusively with human regulatory authorities. |

---

## Verification & Sign-Off Checklist

- [x] All 19 module directories in `backend/src/workbench/modules/` contain active Python implementations.
- [x] Zero README-only stubs remain in the backend codebase.
- [x] Migration chain `0001` through `0016` verified as strictly linear and forward-compatible.
- [x] All 16 operational runbooks formatted and validated.
- [x] Champion/challenger model drift and rule drift evaluation verified against frozen benchmarks.
- [x] Automated access review and expired-assignment sweep tested.
- [x] Handover index completely mapped and cross-referenced.
