# Operational Runbook 10: Audit Log Checkpoint Lag & Hash-Chain Gaps

## 1. Overview & Context
Handles delays or integrity failures in the cryptographic audit ledger (`audit_events`), checkpoint export pipeline, or verification discrepancies between in-database event chains and S3 audit vault archives.

## 2. Symptoms & Triggering Alarms
- CloudWatch Alarm: `AuditCheckpointLagMinutes` (> 15 minutes lag)
- Audit Verifier Error: `STREAM_HASH_MISMATCH` or `GAP_DETECTED_IN_STREAM`
- Scheduled job fails to write signed checkpoint tarball to `audit_vault` S3 bucket.

## 3. Dashboards & Log Queries
- **CloudWatch Logs Insights**:
  ```sql
  fields @timestamp, stream_name, last_sequence, error, calculated_hash, stored_hash
  | filter unit = "audit-worker" and level in ["ERROR", "WARN"]
  ```

## 4. Owner & Escalation Path
- **Primary Owner**: Audit & Compliance Systems Engineer
- **Secondary Escalation**: Lead Security Architect & Regulatory Auditor

## 5. Safe Containment
- If a cryptographic gap is detected, DO NOT attempt to rewrite historical audit rows. PostgreSQL database trigger `wb.immutable_row()` prevents in-place edits and will abort transactions attempting to mutate audit logs.
- Halt automated audit vault archival for affected stream until root cause is identified.

## 6. Diagnostic Steps
1. Run stream verification CLI across all audit streams (`SECURITY`, `REGULATORY`, `SYSTEM`):
   ```bash
   uv run workbench audit verify-all-streams
   ```
2. Identify sequence discrepancy or missing sequence IDs:
   ```bash
   uv run workbench audit detect-sequence-gaps --stream SECURITY
   ```
3. Check KMS key permissions on `audit_key` in AWS IAM.

## 7. Recovery Commands & Reconciliation
1. If checkpoint worker stalled due to task memory or S3 throttling:
   ```bash
   uv run workbench audit export-checkpoint --stream ALL --force-catchup
   ```
2. Verify cryptographic continuity from genesis to stream head:
   ```bash
   uv run workbench audit verify-stream --stream SECURITY
   uv run workbench audit verify-stream --stream REGULATORY
   ```
3. Re-upload signed checkpoint bundle to S3 audit vault:
   ```bash
   uv run workbench audit upload-checkpoint --vault-bucket prod-aicte-audit-vault-prod
   ```

## 8. Post-Recovery Verification
- Check that `AuditCheckpointLagMinutes` metric drops below 5 minutes.
- Verify that S3 audit vault bucket has new timestamped checkpoint file with Object Lock retention applied.

## 9. Actions Requiring Policy / Security Sign-Off
- Acknowledging an irrecoverable cryptographic hash-chain break (requires formal compliance incident filing).
- Authorizing emergency administrative audit key access.
