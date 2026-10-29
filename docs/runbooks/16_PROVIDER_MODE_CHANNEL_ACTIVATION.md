# Operational Runbook 16: Provider Mode & Notification Channel Scope Activation

## 1. Overview & Context
Governs the server-controlled activation of pilot cohorts, promotion from `SIMULATED` to `RESTRICTED_LIVE` or `OFFICIAL_LIVE` provider modes, and enabling outbound notification channels (e.g. SES email alerts).

## 2. Hard Capability Gates (Section 12.5 & Subphase 14.3)
- **Server Gate Enforcement**: A UI request cannot bypass capability gates. All activation requests are strictly validated server-side.
- **Mandatory Advisory Mode**: In pilot and evaluation scopes, `advisory_mode_only` MUST be True. Automated adverse actions are strictly forbidden.
- **Prerequisite Validation**:
  - Live provider mode requires verified production credentials stored in Secrets Manager and a signed statutory MOU/data-sharing agreement.
  - Outbound email requires verified SES production credentials, approved templates, and recipient consent records.

## 3. Owner & Escalation Path
- **Primary Owner**: Institutional Pilot Coordinator & Platform Administrator
- **Authorizing Official**: Regulatory Supervisor (with mandatory TOTP MFA)
- **External Liaison**: Statutory Agency SPOC

## 4. Execution Sequence

### Step 1: Pre-Activation Checklist Verification
Verify that:
1. Cohort institution IDs are approved and registered in `institutions`.
2. Review officers are assigned via `case_assignments` with valid non-expired lifetimes.
3. Target rule release is published and signed off:
   ```bash
   uv run workbench rules list-published
   ```

### Step 2: Server-Side Pilot Scope Activation
Execute authenticated API call via supervisor role with active MFA elevation:
```bash
curl -X POST https://workbench.aicte-india.org/api/v1/operations/pilot-scope \
  -H "Authorization: Bearer <supervisor_mfa_jwt>" \
  -H "Content-Type: application/json" \
  -d '{
    "cohort_id": "PILOT-2026-COHORT-A",
    "institution_ids": ["inst_001", "inst_002"],
    "enabled_rule_release_id": "rel-pub-2026-01",
    "provider_mode": "SIMULATED",
    "outbound_notifications_enabled": false,
    "advisory_mode_only": true,
    "approval_officer_ids": ["officer_sharma", "officer_patel"]
  }'
```

### Step 3: Verifying Capability Gating Rejection
Confirm that unauthorized attempts are rejected:
1. Attempting to set `advisory_mode_only: false` must return `422 CAPABILITY_GATE_VIOLATION`.
2. Attempting to set `provider_mode: "OFFICIAL_LIVE"` without live credentials must return `422 CAPABILITY_GATE_VIOLATION`.
3. Attempting to activate as applicant must return `403 ACCESS_DENIED`.

### Step 4: Verify Public Capabilities Reflection
Verify that `GET /api/v1/capabilities` reflects the newly activated pilot scope:
```bash
curl https://workbench.aicte-india.org/api/v1/capabilities
```
Output must contain:
```json
{
  "pilot_scope_active": true,
  "active_cohort_id": "PILOT-2026-COHORT-A",
  "advisory_mode_only": true,
  "server_gate_enforced": true
}
```

## 5. Post-Activation Verification
- Run automated pilot scope acceptance test suite:
  ```bash
  uv run pytest backend/tests/acceptance/test_phase_14_pilot.py -v
  ```
- Verify immutable audit event:
  ```bash
  uv run workbench audit inspect-events --event-type PILOT_SCOPE_ACTIVATED
  ```

## 6. Actions Requiring Policy / Security Sign-Off
- Transitioning any statutory provider mode to `OFFICIAL_LIVE`.
- Enabling external outbound emails to actual applicant institutional email inboxes.
