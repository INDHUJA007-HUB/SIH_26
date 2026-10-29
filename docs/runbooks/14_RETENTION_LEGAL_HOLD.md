# Operational Runbook 14: Regulatory Retention & Legal Hold Administration

## 1. Overview & Context
Governs the application of statutory data retention schedules (7 years for regulatory evidence, reports, and audit logs) and legal hold freezes on specific institutions or application cases under judicial inquiry, anti-corruption investigation, or appellate review.

## 2. Statutory Policy Rules
- **Non-Deletion Guarantee**: Under an active legal hold, no evidence version, report, finding diff, or audit log may be deleted, purged, or marked with a delete marker.
- **S3 Object Lock Compliance Mode**: Prevents even root AWS accounts from deleting objects prior to the retention date.
- **Selective Legal Hold**: Individual application records can be placed on legal hold without locking unrelated institution records.

## 3. Owner & Escalation Path
- **Primary Owner**: Legal Compliance Officer & Institutional Records Custodian
- **Technical Operator**: Security Platform Engineer
- **Authorization**: AICTE Chief Vigilance Officer (CVO) / Standing Hearing Committee

## 4. Execution Sequence

### 4.1 Applying a Legal Hold to an Application
1. Verify judicial or vigilance notice reference number (e.g. `CVO-INQ-2026-042`).
2. Apply database legal hold status:
   ```bash
   uv run workbench retention place-legal-hold \
     --application-id <application_id> \
     --hold-reference "CVO-INQ-2026-042" \
     --reason "Standing Hearing Committee formal dispute review"
   ```
3. Apply S3 Object Lock Legal Hold on all associated clean evidence, derivative, and report objects:
   ```bash
   uv run workbench storage apply-s3-legal-hold --application-id <application_id> --status ON
   ```

### 4.2 Inspecting Active Legal Holds
Query all active legal holds across the platform:
```bash
uv run workbench retention list-legal-holds
```

### 4.3 Releasing a Legal Hold
1. Requires written sign-off from AICTE Legal Cell.
2. Remove S3 Object Lock Legal Hold:
   ```bash
   uv run workbench storage apply-s3-legal-hold --application-id <application_id> --status OFF
   ```
3. Update database record with release audit event:
   ```bash
   uv run workbench retention release-legal-hold \
     --application-id <application_id> \
     --release-authorization "LEGAL-RELEASE-2026-109"
   ```

## 5. Post-Execution Verification
- Check audit trail for immutable record of hold application / release:
  ```bash
  uv run workbench audit inspect-events --application-id <application_id> --event-type LEGAL_HOLD_APPLIED
  ```
- Attempt test deletion on held object to verify rejection:
  ```bash
  aws s3api delete-object --bucket prod-aicte-clean-prod --key <key> --version-id <version_id>
  # Must fail with AccessDenied / ObjectLockError
  ```

## 6. Actions Requiring Policy / Security Sign-Off
- Authorizing any legal hold release.
- Modifying standard statutory retention periods.
