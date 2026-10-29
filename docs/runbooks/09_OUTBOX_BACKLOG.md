# Operational Runbook 09: Outbox Event Backlog & Relay Recovery

## 1. Overview & Context
Handles accumulation of undelivered events in the transactional `outbox` table due to outbox relay worker crash, database lock contention, or Temporal frontend service degradation.

## 2. Symptoms & Triggering Alarms
- CloudWatch Alarm: `OutboxBacklogAgeHigh` (Oldest undelivered event > 300 seconds)
- Metric: `AICTE/Workbench: OldestUndeliveredEventSeconds`
- Operations table shows newly submitted applications without corresponding workflow executions started.

## 3. Dashboards & Log Queries
- **CloudWatch Logs Insights**:
  ```sql
  fields @timestamp, event_id, event_type, lease_until, delivery_attempts, error
  | filter unit = "outbox-relay"
  | sort delivery_attempts desc
  | limit 50
  ```

## 4. Owner & Escalation Path
- **Primary Owner**: Platform Backend Engineer on-call
- **Secondary Escalation**: Temporal Infrastructure Administrator

## 5. Safe Containment
- Do NOT delete rows from `outbox`. Outbox events are the authoritative committed business receipts.
- Duplicate dispatch is safe: workflow activity definitions use stable business keys and idempotent transaction boundaries.

## 6. Diagnostic Steps
1. Query outbox status via CLI:
   ```bash
   uv run workbench relay status
   ```
2. Check for poison pill event (an event failing continuously with high delivery attempt count):
   ```bash
   uv run workbench relay list-stalled --min-attempts 5
   ```
3. Verify database connection pool health for `wb_relay` role.

## 7. Recovery Commands & Mitigation
1. Clear expired leases on stranded events:
   ```bash
   uv run workbench relay reclaim-expired-leases --timeout-seconds 60
   ```
2. Scale up outbox relay worker instances if volume surge caused backlog:
   ```bash
   aws ecs update-service --cluster prod-aicte-workbench --service outbox-relay --desired-count 4
   ```
3. If a poison pill event is blocked on an unrecoverable payload error, route event to dead-letter storage with audited justification:
   ```bash
   uv run workbench relay dead-letter --event-id <event_id> --reason "Malformed payload schema v0"
   ```
4. Trigger bulk relay processing:
   ```bash
   uv run workbench relay flush --batch-size 100
   ```

## 8. Post-Recovery Verification
- Verify outbox backlog returns to 0:
  ```bash
  uv run workbench relay status
  # Expected: pending_events = 0, oldest_age_seconds < 10
  ```
- Run recovery drill checkpoint 1 verification:
  ```bash
  uv run python backend/tools/recovery_drill.py
  ```

## 9. Actions Requiring Policy / Security Sign-Off
- Dead-lettering an event associated with statutory submission finalization.
