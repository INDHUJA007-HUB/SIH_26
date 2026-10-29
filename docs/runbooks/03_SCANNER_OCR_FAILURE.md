# Operational Runbook 03: Parser, Scanner, and OCR Worker Failures

## 1. Overview & Context
Handles PDF parser crashes (e.g. malformed XRef tables, memory exhaustion), ClamAV daemon outages, PaddleOCR model inference timeout, or font-encoding errors during document intake.

## 2. Symptoms & Triggering Alarms
- CloudWatch Alarm: `ExtractionFailureRateHigh` (> 3% extraction jobs failed)
- Metric: `AICTE/Workbench: ParserTimeoutCount`, `ClamAVDaemonUnavailable`
- Evidence status in database moves to `SCAN_FAILED` or extraction run status is `FAILED`.
- Application UI shows document banner: "Extraction failed - officer manual review required".

## 3. Dashboards & Log Queries
- **CloudWatch Logs Insights**:
  ```sql
  fields @timestamp, evidence_id, error_type, memory_mb, duration_s
  | filter unit in ["scan-worker", "document-worker"] and level = "ERROR"
  | stats count(*) by error_type
  ```

## 4. Owner & Escalation Path
- **Primary Owner**: Document Processing Engineer on-call
- **Secondary Escalation**: Machine Learning / Computer Vision Lead

## 5. Safe Containment (Fail-Closed)
- Under no circumstances may an unscanned or extraction-failed document be promoted directly to `ACCEPTED` without manual review.
- The `wb.intake_guard()` trigger in PostgreSQL will automatically prevent quarantine leakage.
- If ClamAV service is unresponsive, the system automatically fails closed to `SCAN_FAILED`.

## 6. Diagnostic Steps
1. Verify ClamAV container health:
   ```bash
   uv run workbench scanner health-check
   ```
2. Determine if failure is file-specific (e.g. corrupted PDF stream) or worker pool outage:
   ```bash
   uv run workbench extraction inspect-failure --evidence-id <evidence_id>
   ```
3. Test parser sandbox against safe synthetic sample:
   ```bash
   uv run workbench parser probe-sandbox
   ```

## 7. Recovery Commands & Mitigation
1. If ClamAV daemon is degraded, restart the scanning service:
   ```bash
   aws ecs update-service --cluster prod-aicte-workbench --service scan-worker --force-new-deployment
   ```
2. Re-queue stranded scans once scanner returns to service:
   ```bash
   uv run workbench scanner retry-failed-scans --max-age-hours 6
   ```
3. If document text layer is unreadable or malformed, fall back to high-resolution rendering and OCR pipeline:
   ```bash
   uv run workbench extraction reprocess --evidence-id <evidence_id> --force-ocr
   ```
4. If the document is fundamentally unparsable (encrypted or corrupted by applicant), create an officer clarification task:
   ```bash
   uv run workbench tasks create-applicant-query --evidence-id <evidence_id> --reason "Unreadable PDF file structure"
   ```

## 8. Post-Recovery Verification
- Verify `extraction_runs` status transitions to `COMPLETED`.
- Confirm `extracted_fields` has non-zero populated critical fields (e.g., land acres, bandwidth).
- Check that `evidence` status transitions to `ACCEPTED`.

## 9. Actions Requiring Policy / Security Sign-Off
- Bypassing anti-malware scan for a specific high-priority applicant submission.
- Manually adjusting OCR extraction confidence thresholds across all applications.
