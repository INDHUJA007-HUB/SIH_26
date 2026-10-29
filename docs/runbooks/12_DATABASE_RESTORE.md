# Operational Runbook 12: Point-In-Time Database Restore & Reconciliation

## 1. Overview & Context
Procedures for recovering the domain PostgreSQL RDS database and Temporal persistence RDS database to a point-in-time (PITR) following catastrophic storage failure, accidental data truncation, or database host corruption.

## 2. Key Constraints & Guarantees (Section 12.6)
- **Target In-Region Objectives**: RPO $\le 5\text{ minutes}$, RTO $\le 60\text{ minutes}$.
- **Differential Restore Points**: Domain DB and Temporal DB restore points may differ. The system tolerates this explicitly via idempotent workflow activities and stable business keys.
- **Authoritative Source of Truth**: Committed business receipts reside in the domain database; workflow executions reconcile against domain state.

## 3. Owner & Escalation Path
- **Primary Owner**: Lead Database Administrator & Infrastructure Platform Lead
- **Incident Commander**: Lead Architect
- **Executive Authorization**: Service Owner & CISO

## 4. Execution Sequence

### Step 1: Declare Incident & Halt Ingress
1. Point public ALB to maintenance error page (drain active connections):
   ```bash
   aws elbv2 modify-listener --listener-arn <alb_listener_arn> --default-actions Type=fixed-response,FixedResponseConfig="{StatusCode=503,ContentType=text/plain,MessageBody='Scheduled maintenance and database recovery in progress'}"
   ```
2. Stop ECS worker tasks to prevent conflicting writes:
   ```bash
   aws ecs update-service --cluster prod-aicte-workbench --service outbox-relay --desired-count 0
   aws ecs update-service --cluster prod-aicte-workbench --service workflow-worker --desired-count 0
   ```

### Step 2: Trigger Point-In-Time Restore (PITR) in RDS
1. Restore domain database to target timestamp (e.g. `2026-10-28T14:00:00Z`):
   ```bash
   aws rds restore-db-instance-to-point-in-time \
     --source-db-instance-identifier prod-aicte-domain-db \
     --target-db-instance-identifier prod-aicte-domain-db-restored \
     --restore-time 2026-10-28T14:00:00Z \
     --db-subnet-group-name production-db-subnet-group \
     --vpc-security-group-ids <db_sg_id>
   ```
2. Restore Temporal persistence database to the closest available recovery point:
   ```bash
   aws rds restore-db-instance-to-point-in-time \
     --source-db-instance-identifier prod-aicte-temporal-db \
     --target-db-instance-identifier prod-aicte-temporal-db-restored \
     --restore-time 2026-10-28T14:00:00Z
   ```

### Step 3: Switch Endpoints & Update Secrets
1. Rename restored instance or update connection secret in AWS Secrets Manager:
   ```bash
   aws secretsmanager put-secret-value \
     --secret-id production/aicte/database/credentials \
     --secret-string file://restored_credentials.json
   ```

### Step 4: Run Reconciliation Drill (Section 12.6)
Execute the automated recovery and reconciliation script to reconcile outbox, workflow cursors, S3 object versions, and audit chain continuity:
```bash
uv run python backend/tools/recovery_drill.py
```
Ensure all 4 checkpoints pass:
- Checkpoint 1: Outbox lease recovery & deduplication
- Checkpoint 2: Audit cryptographic chain integrity
- Checkpoint 3: Quarantine isolation & object versioning
- Checkpoint 4: Workflow cursor reconciliation.

### Step 5: Resume Services & Reopen Ingress
1. Scale up ECS workers:
   ```bash
   aws ecs update-service --cluster prod-aicte-workbench --service outbox-relay --desired-count 2
   aws ecs update-service --cluster prod-aicte-workbench --service workflow-worker --desired-count 4
   ```
2. Re-enable normal routing on ALB:
   ```bash
   aws elbv2 modify-listener --listener-arn <alb_listener_arn> --default-actions Type=forward,TargetGroupArn=<api_tg_arn>
   ```

## 5. Post-Recovery Verification
- Run acceptance test suite:
  ```bash
  uv run pytest backend/tests/acceptance/test_e2e_acceptance.py -v
  ```
- Record achieved RPO and RTO in incident post-mortem.

## 6. Actions Requiring Policy / Security Sign-Off
- Authorizing PITR rollback that results in any non-zero loss of submitted applications.
- Re-opening public intake after major database recovery.
