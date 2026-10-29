# Operational Runbook: Pilot Go/No-Go Decision Protocol and Readiness Gate Checklist

- **Document ID**: `OP-RUNBOOK-GO-NO-GO`
- **Version**: `1.0.0`
- **Owner**: Operations & Pilot Governance Directorate
- **Applicability**: Production Deployment / Staging / Integration Environments
- **Review Cadence**: Prior to every major pilot onboarding or scope amendment

---

## 1. Executive Summary and Policy Invariants

Before any institutional pilot scope is activated or amended in production via `POST /api/v1/operations/pilot-scope`, the Joint Review Committee (comprising the Lead Reliability Engineer, Lead Security Architect, Data Governance Officer, and Pilot Institution Lead) must convene and unanimously sign off on this Go/No-Go Decision Protocol.

### Non-Negotiable Invariants:
1. **Advisory Mode Only**: The platform is restricted to human-in-the-loop decision support (`advisory_mode_only = true`). Direct automated adverse determination on any applicant application is strictly disabled by database constraints and software invariant checks.
2. **Provider Mode Parameterization**: Unless certified by the Joint Committee with signed bilateral data-sharing contracts, third-party source providers (such as academic registries, tax portals, or credit bureaus) must run in `SIMULATED` or read-only certified modes.
3. **Outbound Notification Safeguards**: Outbound SMS/Email dispatching to live applicants during the pilot phase requires cryptographic approval and verification token registration.
4. **Zero Open Tier-1 Security Vulnerabilities**: No unresolved CVEs or high/critical static analysis findings across core dependencies or infrastructure configurations.

---

## 2. Go/No-Go Readiness Assessment Dimensions

| Gate Dimension | Lead Reviewer | Acceptance Threshold | Status |
| :--- | :--- | :--- | :--- |
| **1. Policy, Governance & Scope** | Pilot Institution Lead | - Signed bilateral pilot agreement<br>- Named supervisor and pilot officer rosters<br>- Defined max daily application quota (capped $\le 500$)<br>- Explicit list of pilot program IDs | [ ] PENDING / PASS |
| **2. Security & Trust-Zone Isolation** | Security Architect | - All 6 trust zones strictly segmented in Terraform<br>- Zero scanner/document worker egress to issuer network<br>- Runtime DB user lacks `BYPASSRLS` and table ownership<br>- KMS encryption configured with envelope keys | [ ] PENDING / PASS |
| **3. Infrastructure & Deployment** | Lead DevOps / SRE | - Multi-AZ RDS PostgreSQL deployed and synchronized<br>- Versioned S3 buckets deployed with Object Lock active on audit vault<br>- VPC private link endpoints active for S3, Secrets Manager, KMS<br>- OTel telemetry collector ingestion verified | [ ] PENDING / PASS |
| **4. Database & Migration Linearity** | Lead Data Architect | - Linear Alembic migration chain verified (`0001` through `0015`)<br>- Zero destructive DDL commands (`DROP TABLE`, `DROP COLUMN`)<br>- Expand/contract compatibility tested for zero-downtime canary rollback | [ ] PENDING / PASS |
| **5. Reliability & Performance** | QA & Performance Lead | - Full acceptance & failure-injection suite passes ($168/168$ tests)<br>- P95 API latency $\le 300\text{ ms}$ under baseline load<br>- Worker failover recovery tested under unacknowledged tasks<br>- Outbox event replay deduplication verified | [ ] PENDING / PASS |
| **6. Operational Runbooks & On-Call** | Operations Lead | - All 16 operational runbooks validated and published in repository<br>- On-call rotation roster populated with secondary escalation contacts<br>- Canary rollback rehearsal executed cleanly within 5 minutes | [ ] PENDING / PASS |

---

## 3. Detailed Verification Checklists

### 3.1 Trust-Zone & Infrastructure Verification (Subphase 14.1)
Execute the infrastructure validation tool:
```bash
python backend/tools/check_infra.py
```
- [ ] Checkpoint 1: Networking & VPC modular configurations present
- [ ] Checkpoint 2: Storage S3 buckets present with versioning and audit-vault Object Lock
- [ ] Checkpoint 3: Multi-AZ RDS configurations with encrypted storage and non-default parameter groups
- [ ] Checkpoint 4: ECS Fargate deployment definitions with 6 distinct IAM task roles
- [ ] Checkpoint 5: Scanner/OCR worker policy contains zero external egress or rule publishing permissions
- [ ] Checkpoint 6: Runtime DB role (`wb_app`, `wb_worker`) is non-owner and lacks `BYPASSRLS`
- [ ] Checkpoint 7: CloudWatch log groups & OTel collector configurations present
- [ ] Checkpoint 8: All 3 environment configurations (`integration`, `staging`, `production`) present and modularized

### 3.2 Release & Migration Safety Verification (Subphase 14.2)
Execute migration and release verification tools:
```bash
python backend/tools/verify_migrations.py
python backend/tools/release_manifest.py --action generate --env production
python backend/tools/release_manifest.py --action verify --env production
python backend/tools/rehearse_rollback.py
```
- [ ] Migration chain verified as strictly linear with no branching
- [ ] Zero destructive DDL in current migration release
- [ ] Release manifest generated and cryptographically verified with HMAC-SHA256 signature
- [ ] Canary traffic shifting and circuit-breaker rollback rehearsal completes in $< 300\text{ s}$ without service disruption or schema divergence

### 3.3 Pilot Scope & Capabilities Verification (Subphase 14.3)
Execute the Phase 14 pilot test suite:
```bash
pytest backend/tests/acceptance/test_phase_14_pilot.py -v
```
- [ ] Non-supervisor activation rejected with `403 Forbidden`
- [ ] Missing MFA token rejected with `403 Forbidden`
- [ ] Attempted bypass of advisory mode (`advisory_mode_only = false`) rejected by database constraint and API gate (`422 Unprocessable Entity`)
- [ ] Activation with unverified live provider or unverified outbound notification rejected with `422 Unprocessable Entity`
- [ ] Active scope successfully registered, audited in `audit_events`, and reflected on `GET /api/v1/capabilities` with `server_gate_enforced = true`

### 3.4 Operational Runbook Coverage (Subphase 14.4)
Verify all 16 runbooks are accessible to operators:
- [ ] `01_SOURCE_OUTAGE_RATE_LIMIT.md`: Source provider outages and circuit breaker trips
- [ ] `02_STUCK_WORKFLOW.md`: Stuck or non-advancing intake/assessment workflows
- [ ] `03_SCANNER_OCR_FAILURE.md`: Malware scanner, OCR, or text extraction worker failure
- [ ] `04_UNSAFE_FILE.md`: Malware detection and quarantine containment
- [ ] `05_FAILED_REPORT.md`: Report generation failure or digest mismatch
- [ ] `06_SUSPECTED_CROSS_INSTITUTION_EXPOSURE.md`: RLS or tenancy isolation breach investigation
- [ ] `07_CREDENTIAL_KEY_ROTATION.md`: Secrets Manager & KMS key rotation
- [ ] `08_RULE_ROLLBACK.md`: Emergency rollback of published rule releases
- [ ] `09_OUTBOX_BACKLOG.md`: Transactional outbox dispatch backlog
- [ ] `10_AUDIT_CHECKPOINT_GAP.md`: Audit checkpoint gap and hash chain reconciliation
- [ ] `11_STORAGE_MISMATCH.md`: S3 storage hash or digest divergence
- [ ] `12_DATABASE_RESTORE.md`: Point-in-time recovery and snapshot restoration
- [ ] `13_REGIONAL_RECOVERY.md`: Cold standby regional failover protocol
- [ ] `14_RETENTION_LEGAL_HOLD.md`: Legal hold application and retention enforcement
- [ ] `15_DEPLOYMENT_ROLLBACK.md`: Canary and container deployment rollback
- [ ] `16_PROVIDER_MODE_CHANNEL_ACTIVATION.md`: Controlled activation of live providers and notification channels

---

## 4. Formal Sign-Off Table

| Role | Signatory Name | Decision (GO / NO-GO) | Timestamp (UTC) | Signature / Approval Hash |
| :--- | :--- | :--- | :--- | :--- |
| **Lead SRE / DevOps** | | [ ] GO / [ ] NO-GO | | |
| **Security Architect** | | [ ] GO / [ ] NO-GO | | |
| **Lead Data Architect** | | [ ] GO / [ ] NO-GO | | |
| **Pilot Institution Lead** | | [ ] GO / [ ] NO-GO | | |

*Rule*: A single **NO-GO** vote halts pilot deployment immediately and triggers an Incident Review.
