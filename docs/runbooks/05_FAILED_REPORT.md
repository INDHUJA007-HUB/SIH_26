# Operational Runbook 05: Evaluation Report Generation Failure & Redaction Errors

## 1. Overview & Context
Triggered when ReportLab or Jinja2 PDF rendering fails (e.g., out-of-memory, font substitution error, missing template asset) or when an applicant report fails automated redaction checks (detecting internal notes or other-tenant PII).

## 2. Symptoms & Triggering Alarms
- CloudWatch Alarm: `ReportGenerationFailureHigh` (> 1% failures)
- Audit Event: `REPORT_GENERATION_FAILED`, `REPORT_REDACTION_VIOLATION`
- Application UI shows report status `FAILED` or returns 500 on `GET /api/v1/reports/{id}`.

## 3. Dashboards & Log Queries
- **CloudWatch Logs Insights**:
  ```sql
  fields @timestamp, report_id, run_id, audience, error
  | filter unit = "report-worker" and level = "ERROR"
  ```

## 4. Owner & Escalation Path
- **Primary Owner**: Reporting & Document Services Engineer
- **Secondary Escalation**: Product Quality Lead

## 5. Safe Containment (Fail-Closed)
- If a redaction rule check fails, the report is NOT saved to the public `reports` S3 bucket.
- No partial or unredacted PDF is served to applicant actors.

## 6. Diagnostic Steps
1. Inspect the evaluation run and finding data backing the report:
   ```bash
   uv run workbench reports inspect-run --run-id <run_id>
   ```
2. Verify template compilation and font embedding:
   ```bash
   uv run workbench reports test-template --audience APPLICANT
   ```
3. Check memory consumption in ReportLab container task.

## 7. Recovery Commands & Mitigation
1. Re-render the report with debug trace enabled:
   ```bash
   uv run workbench reports render --run-id <run_id> --audience APPLICANT --force
   ```
2. If font rendering caused memory exhaustion, re-render using fallback system fonts:
   ```bash
   uv run workbench reports render --run-id <run_id> --audience APPLICANT --fallback-fonts
   ```
3. Re-verify SHA-256 hash and audience separation:
   ```bash
   uv run workbench reports verify-integrity --report-id <report_id>
   ```

## 8. Post-Recovery Verification
- Download the generated report as an applicant actor to ensure internal officer notes are completely absent:
  ```bash
  uv run workbench reports verify-redaction --report-id <report_id> --actor applicant
  ```

## 9. Actions Requiring Policy / Security Sign-Off
- Overriding automated redaction check failures.
- Altering the official regulatory disclaimer text in generated reports.
