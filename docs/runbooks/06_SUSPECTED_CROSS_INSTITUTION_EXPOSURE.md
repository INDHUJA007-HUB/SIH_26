# Operational Runbook 06: Suspected Cross-Institution Data Exposure & BOLA Alarm

## 1. Overview & Context
Triggered upon any suspected or detected breach of multi-tenant boundaries (e.g. Row Level Security policy failure, BOLA/BOPLA attempt, unassigned reviewer accessing unauthorized cases, or cross-tenant identifier leak).

## 2. Symptoms & Triggering Alarms
- CloudWatch Alarm: `CrossTenantAccessAttemptsSpike` (> 3 attempts in 5 minutes)
- PostgreSQL Log: `insufficient_privilege` or `raise_exception: access is not permitted`
- Audit Event: `ACCESS_DENIED`, `BOLA_VIOLATION_BLOCKED`
- User Report: User claims to see another institution's name, documents, or reports in portal.

## 3. Dashboards & Log Queries
- **Security Operations Dashboard**: `AICTE-Security-Audit`
- **CloudWatch Logs Insights**:
  ```sql
  fields @timestamp, actor_id, institution_id, requested_resource, http_status, error_code
  | filter error_code in ["ACCESS_DENIED", "BOLA_VIOLATION"]
  | sort @timestamp desc
  ```

## 4. Owner & Escalation Path
- **Primary Owner**: Information Security Lead (Incident Commander)
- **Secondary Escalation**: Lead Architect, System Administrator, CISO
- **Regulatory Notification**: AICTE Legal and Compliance Directorate

## 5. Safe Containment (Immediate Quarantine)
1. Immediately revoke active session of the offending actor identity:
   ```bash
   uv run workbench identity revoke-session --session-id <session_id> --reason "Suspected tenant boundary probing"
   ```
2. If RLS policy integrity is questionable, place API in maintenance read-only mode immediately:
   ```bash
   uv run workbench system set-mode --mode READ_ONLY --reason "Security perimeter review"
   ```

## 6. Diagnostic Steps
1. Trace the exact API endpoint, parameters, and database query:
   ```bash
   uv run workbench audit trace-request --request-id <request_id>
   ```
2. Verify Row Level Security status on affected tables in PostgreSQL:
   ```bash
   uv run workbench security verify-rls-status
   ```
3. Check `case_assignments` and `memberships` for accidental over-privileged role grants.

## 7. Recovery Commands & Mitigation
1. Revoke any rogue or improperly scoped case assignment:
   ```bash
   uv run workbench identity revoke-assignment --assignment-id <assignment_id>
   ```
2. If code bug in API handler allowed bypass of tenant filter before reaching RLS, deploy hotfix or roll back deployment (see Runbook 15).
3. Validate audit log continuity:
   ```bash
   uv run workbench audit verify-stream --stream SECURITY
   ```
4. Restore API to normal operating mode:
   ```bash
   uv run workbench system set-mode --mode OPERATIONAL
   ```

## 8. Post-Recovery Verification
- Execute automated OWASP security suite:
  ```bash
  uv run pytest backend/tests/security/test_owasp_security.py -v
  ```
- Generate formal Data Protection Incident Report (DPIR) specifying affected IDs, exact timestamps, and exposure status (confirmed zero leak vs confirmed exposure).

## 9. Actions Requiring Policy / Security Sign-Off
- Confirming whether statutory data breach notification protocols must be triggered.
- Unblocking a suspended institutional user account.
