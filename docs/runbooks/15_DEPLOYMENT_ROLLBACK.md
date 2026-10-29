# Operational Runbook 15: Application Deployment & Worker Rollback

## 1. Overview & Context
Procedures for rolling back an application or worker deployment following canary failure, critical defect emergence, or latency degradation in production or staging.

## 2. Key Rollback Principles (Section 12.5)
- **Immutable Image Promotion**: Rollback does not rebuild code; it redeploys previously tested, signed container image digests.
- **Database Expand/Contract Safety**: Forward migrations are designed so older worker images continue running safely without schema errors.
- **Worker Drain**: Running activities and long tasks are allowed to finish or gracefully checkpoint rather than being forcibly aborted.

## 3. Symptoms & Triggering Alarms
- CloudWatch Alarm: `APIHigh5xxErrors`
- CloudWatch Alarm: `WorkflowTaskBacklogSurge`
- High latency ($p95 > 500\text{ms}$ on simple writes)
- Unhandled exceptions during evaluation or extraction runs.

## 4. Owner & Escalation Path
- **Primary Owner**: Release Engineer on-call
- **Incident Commander**: Lead Platform Engineer

## 5. Rollback Procedure

### Step 1: Automated Canary Halt
If canary deployment is in progress (e.g. 10% traffic to candidate), halt traffic shift immediately:
```bash
uv run python backend/tools/rehearse_rollback.py
```

### Step 2: Retrieve Previous Stable Signed Release Manifest
Identify the last known good release manifest:
```bash
aws s3 cp s3://prod-aicte-audit-vault-prod/releases/manifests/REL-PRODUCTION-1.0.0.json ./last_stable_manifest.json
uv run python backend/tools/release_manifest.py --verify
```

### Step 3: Roll Back ECS Service Task Definitions
Update ECS services to use the previous container image digests from the verified manifest:
```bash
# Update API service
aws ecs update-service \
  --cluster prod-aicte-workbench \
  --service api \
  --task-definition production-aicte-api:previous

# Update Document & Worker services
aws ecs update-service \
  --cluster prod-aicte-workbench \
  --service document-worker \
  --task-definition production-aicte-document-worker:previous

aws ecs update-service \
  --cluster prod-aicte-workbench \
  --service workflow-worker \
  --task-definition production-aicte-workflow-worker:previous
```

### Step 4: Verify Database Compatibility
Confirm that the database schema requires no down-migrations (expand/contract validation):
```bash
uv run python backend/tools/verify_migrations.py
```
*Note: Do not run `alembic downgrade` unless expressly instructed and signed off by the DBA. The schema is backward-compatible with older worker versions.*

## 6. Post-Rollback Verification
1. Verify API health check:
   ```bash
   curl -f https://workbench.aicte-india.org/api/v1/health
   ```
2. Confirm error rates return to normal baseline (< 0.1%):
   ```bash
   aws cloudwatch get-metric-data --metric-data-queries file://health_query.json
   ```
3. Run acceptance smoke test:
   ```bash
   uv run pytest backend/tests/test_api.py -v
   ```

## 7. Actions Requiring Policy / Security Sign-Off
- Executing a destructive database down-migration.
- Halting production intake during official submission deadline hours.
