# Operational Runbook 04: Unsafe File Detection & Malware Quarantine Isolation

## 1. Overview & Context
Triggered when ClamAV anti-malware detects a malicious signature, embedded macro, executable payload, ZIP bomb, or script exploit in an uploaded document or media asset.

## 2. Symptoms & Triggering Alarms
- CloudWatch Alarm: `MalwareDetectedAlert` (High Severity)
- Metric: `AICTE/Workbench: MalwareSignatureMatchedCount`
- Audit Event: `MALWARE_DETECTED_QUARANTINE_REJECTED`
- Evidence version status transitions permanently to `REJECTED`.

## 3. Dashboards & Log Queries
- **Security Operations Dashboard**: `AICTE-Security-Audit`
- **CloudWatch Logs Insights**:
  ```sql
  fields @timestamp, upload_id, evidence_id, institution_id, malware_signature, ip_address
  | filter unit = "scan-worker" and event = "malware_detected"
  ```

## 4. Owner & Escalation Path
- **Primary Owner**: Information Security Incident Response Team (InfoSec / SOC)
- **Secondary Escalation**: Lead Platform Architect
- **Notification**: Chief Information Security Officer (CISO) and Institutional Review Officer

## 5. Safe Containment (Immediate Automated Lockdown)
- Automated Trigger: S3 object in `quarantine` bucket is tagged `QuarantineStatus=INFECTED`.
- Access Policy: S3 bucket policy and PostgreSQL database trigger `wb.intake_guard()` immediately reject any request to read, stream, or copy this object to clean storage (`403 FORBIDDEN`).
- No derivative rendering, OCR, or thumbnail generation is permitted.

## 6. Diagnostic Steps
1. Identify submitting actor, IP address, and application context:
   ```bash
   uv run workbench security inspect-threat --upload-id <upload_id>
   ```
2. Verify signature name (e.g. `Eicar-Test-Signature`, `Win.Trojan.Exploit-1029`).
3. Check if same actor or IP submitted multiple files across other application slots:
   ```bash
   uv run workbench security find-actor-uploads --actor-id <actor_id>
   ```

## 7. Recovery Commands & Protocol
1. Mark the slot as `REJECTED_INFECTED` with audited rationale:
   ```bash
   uv run workbench security confirm-rejection --evidence-id <evidence_id> --notes "Malware confirmed by security scan"
   ```
2. Notify the applicant institutional coordinator securely via in-app alert (without technical exploit payload details):
   ```bash
   uv run workbench alerts send-security-notice --institution-id <institution_id> --template MALWARE_FILE_REJECTED
   ```
3. Open a scoped response window for the applicant to re-upload a clean statutory file within official timelines.
4. Schedule infected object deletion following digital forensics preservation (standard: 30 days retention in isolated quarantine bucket, then lifecycle purge).

## 8. Post-Recovery Verification
- Attempt reading the object via API to verify fail-closed behavior:
  ```bash
  uv run workbench delivery probe --evidence-id <evidence_id>
  # Must return 403 Forbidden or 404 Not Found
  ```
- Confirm audit chain integrity:
  ```bash
  uv run workbench audit verify-stream --stream SECURITY
  ```

## 9. Actions Requiring Policy / Security Sign-Off
- Overriding a malware detection as a false positive.
- Forwarding an infected sample to an external cybersecurity agency for deep forensic analysis.
