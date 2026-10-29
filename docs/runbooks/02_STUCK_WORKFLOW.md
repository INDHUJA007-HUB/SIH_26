# Operational Runbook 02: Stuck Workflow Orchestration & Task Reclaim

## 1. Overview & Context
Applies when Temporal workflows or asynchronous outbox event processing stall, workflow worker leases expire without activity completion, or workflow histories exceed memory limits.

## 2. Symptoms & Triggering Alarms
- CloudWatch Alarm: `WorkflowScheduleDelayHigh` (> 60 seconds)
- Metric: `Temporal: WorkflowTaskScheduleToStartTimeout`
- Oldest pending operation age in `operations` table exceeds 30 minutes with status `IN_PROGRESS`.
- Temporal UI displays running executions with no recent event progress.

## 3. Dashboards & Log Queries
- **Temporal Web UI**: `https://temporal.internal:8233/namespaces/aicte-workbench/workflows`
- **CloudWatch Logs Insights**:
  ```sql
  fields @timestamp, workflow_id, run_id, activity_type, error
  | filter unit = "workflow-worker" and level in ["ERROR", "WARN"]
  | sort @timestamp desc
  | limit 50
  ```

## 4. Owner & Escalation Path
- **Primary Owner**: Platform Backend Engineer
- **Secondary Escalation**: Temporal Systems Administrator

## 5. Safe Containment
- Pause automated outbox event dispatch for affected workflow type to avoid compounding backlogs:
  ```bash
  uv run workbench relay pause --queue default
  ```
- Do not terminate running database transactions manually without inspecting lock holders.

## 6. Diagnostic Steps
1. Query stalled operations directly via CLI:
   ```bash
   uv run workbench operations list --status IN_PROGRESS --older-than-minutes 30
   ```
2. Inspect worker pool health and memory saturation in ECS Fargate:
   ```bash
   uv run workbench cluster status --unit workflow-worker
   ```
3. Check for poison pill inputs (e.g. malformed JSON or circular document dependencies).

## 7. Recovery Commands & Reconciliation
1. Signal workflow heartbeats or trigger activity-level timeout retry:
   ```bash
   uv run workbench workflow signal --id <workflow_id> --signal retry_stalled_activity
   ```
2. If worker crashed and left stranded lock in `operations`, trigger lease reclamation:
   ```bash
   uv run workbench operations reclaim-stranded-leases --max-age-minutes 15
   ```
3. For irrecoverable workflow execution, terminate execution and re-dispatch from committed outbox receipt:
   ```bash
   uv run workbench workflow cancel --id <workflow_id> --reason "Operator manual reset due to timeout"
   uv run workbench operations retry --operation-id <operation_id>
   ```

## 8. Post-Recovery Verification
- Check that `operations` status updates to `COMPLETED` and receipt hash matches payload.
- Confirm Temporal workflow execution status updates to `Completed`.
- Resume outbox relay:
  ```bash
  uv run workbench relay resume --queue default
  ```

## 9. Actions Requiring Policy / Security Sign-Off
- Force-cancelling a workflow during final applicant submission cut-off window.
- Re-executing workflows that involve external financial or irreversible notification side effects.
