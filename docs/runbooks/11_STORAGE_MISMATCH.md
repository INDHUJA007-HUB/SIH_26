# Operational Runbook 11: Object Storage & Metadata Versioning Mismatch

## 1. Overview & Context
Handles discrepancies between the metadata recorded in PostgreSQL (`evidence.clean_key`, `evidence.clean_version`, `evidence.sha256`) and the actual physical objects stored in Amazon S3 (e.g. missing object version, size mismatch, or checksum calculation divergence).

## 2. Symptoms & Triggering Alarms
- CloudWatch Alarm: `S3MetadataIntegrityMismatch`
- HTTP 409 Conflict: `OBJECT_VERSION_MISMATCH` during evidence delivery or extraction
- Worker Error: S3 HeadObject returns version ID differing from pinned database version.

## 3. Dashboards & Log Queries
- **CloudWatch Logs Insights**:
  ```sql
  fields @timestamp, evidence_id, clean_key, clean_version, s3_error
  | filter unit = "evidence-delivery" and level = "ERROR"
  ```

## 4. Owner & Escalation Path
- **Primary Owner**: Platform Storage Engineer on-call
- **Secondary Escalation**: Lead Database Administrator

## 5. Safe Containment (Fail-Closed)
- Under no circumstances may an unverified or mismatched S3 object be served to a review officer or processed by extraction workers.
- The delivery service halts transfer immediately upon checksum or version discrepancy.

## 6. Diagnostic Steps
1. Perform HeadObject on S3 to inspect actual metadata:
   ```bash
   aws s3api head-object --bucket prod-aicte-clean-prod --key <clean_key> --version-id <clean_version>
   ```
2. Compute actual SHA-256 hash of object in S3:
   ```bash
   uv run workbench storage compute-s3-hash --bucket prod-aicte-clean-prod --key <clean_key> --version-id <clean_version>
   ```
3. Compare against stored row in `evidence` table:
   ```bash
   uv run workbench evidence inspect --id <evidence_id>
   ```

## 7. Recovery Commands & Reconciliation
1. If the database points to an obsolete version due to concurrent upload overwrite, restore pinned version pointer:
   ```bash
   uv run workbench storage reconcile-pinned-version --evidence-id <evidence_id> --correct-version <clean_version>
   ```
2. If S3 object is missing but preserved in quarantine:
   ```bash
   uv run workbench storage re-promote-quarantine --evidence-id <evidence_id>
   ```
3. If physical bytes in S3 were corrupted, invalidate cached derivatives and re-extract from original quarantined master:
   ```bash
   uv run workbench extraction purge-derivatives --evidence-id <evidence_id>
   uv run workbench extraction reprocess --evidence-id <evidence_id>
   ```

## 8. Post-Recovery Verification
- Download evidence version via API and verify byte-for-byte SHA-256 match:
  ```bash
  uv run workbench delivery verify-integrity --evidence-id <evidence_id>
  ```
- Run automated failure injection test:
  ```bash
  uv run pytest backend/tests/acceptance/test_failure_injection.py -k "test_object_version_mismatch"
  ```

## 9. Actions Requiring Policy / Security Sign-Off
- Manually updating the SHA-256 checksum of an accepted evidence record in database.
