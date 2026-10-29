# Operational Runbook 07: Credential & Encryption Key Rotation

## 1. Overview & Context
Procedures for routine or emergency rotation of:
1. Database passwords (`wb_admin`, `wb_app`, `wb_worker`)
2. AWS KMS Customer Managed Keys (`app_key`, `audit_key`)
3. JWT Signing Keys & Webhook HMAC Secrets
4. External statutory provider API tokens / client credentials.

## 2. Triggering Scenarios
- **Routine Rotation**: Every 90 days as per regulatory compliance mandate.
- **Emergency Rotation**: Suspected compromise of credentials, engineer offboarding, or unauthorized access attempt.

## 3. Owner & Escalation Path
- **Primary Owner**: Platform Security Engineer & Database Administrator
- **Secondary Escalation**: Lead Architect
- **Approval**: Information Security Officer

## 4. Safe Rotation Sequence (Zero-Downtime Envelope Strategy)

### 4.1 Database Password Rotation
1. Update password in AWS Secrets Manager:
   ```bash
   aws secretsmanager rotate-secret --secret-id prod/aicte/database/credentials
   ```
2. Trigger rolling restart of application tasks to consume new credential:
   ```bash
   aws ecs update-service --cluster prod-aicte-workbench --service api --force-new-deployment
   ```

### 4.2 AWS KMS CMK Rotation
1. Enable automatic annual rotation:
   ```bash
   aws kms enable-key-rotation --key-id alias/production-aicte-app
   ```
2. For emergency rotation, generate new CMK alias and update Terraform configuration, keeping previous key enabled for decrypting historical ciphertext.

### 4.3 JWT Signing Key & Webhook HMAC Secret Rotation
1. Deploy new key version alongside existing key (dual-key grace period: 24 hours):
   ```bash
   uv run workbench secrets add-jwt-key --key-id v2 --secret <new_secret>
   ```
2. Verify token issuance uses `v2` while token validation accepts `v1` and `v2`.
3. After 24 hours (maximum token lifetime), retire `v1`:
   ```bash
   uv run workbench secrets retire-jwt-key --key-id v1
   ```

### 4.4 Statutory Provider Credentials
1. Update secret in AWS Secrets Manager:
   ```bash
   aws secretsmanager put-secret-value --secret-id prod/aicte/connectors/providers --secret-string file://new_tokens.json
   ```
2. Verify connectivity with immediate probe:
   ```bash
   uv run workbench connector probe --provider AICTE_HISTORICAL
   ```

## 5. Post-Rotation Verification
- Check database connection pool health:
  ```bash
  uv run workbench database health-check
  ```
- Run automated end-to-end authentication tests:
  ```bash
  uv run pytest backend/tests/test_api.py -k "test_fixture_uses_server_assignment"
  ```

## 6. Actions Requiring Policy / Security Sign-Off
- Deleting an older KMS key version (irreversible loss of historical encrypted objects).
- Rotating emergency break-glass credentials.
