# Operational Runbook 01: Statutory Source Outage & Rate Limiting

## 1. Overview & Context
Handles upstream statutory provider unavailability, HTTP 429/503 responses, network timeouts, or rate limit quota exhaustion (e.g., AICTE portal, Digilocker, State Higher Education registries, Municipal Fire Safety portals).

## 2. Symptoms & Triggering Alarms
- CloudWatch Alarm: `ProviderErrorRateSurge` (> 5% failures over 5 minutes)
- CloudWatch Metric: `AICTE/Workbench: ProviderRequestTimeoutCount`
- Queue Age: `connector_worker` task backlog exceeds 10 minutes
- User Impact: Pending verification status remains in `VERIFICATION_PENDING` or transitions to `SOURCE_UNAVAILABLE`.

## 3. Dashboards & Log Queries
- **CloudWatch Dashboard**: `AICTE-Workbench-Connectors`
- **CloudWatch Logs Insights**:
  ```sql
  fields @timestamp, provider_code, status_code, error_message, request_fingerprint
  | filter unit = "connector-worker" and level = "ERROR"
  | stats count(*) by provider_code, status_code
  ```

## 4. Owner & Escalation Path
- **Primary Owner**: Platform Integration Engineer on-call
- **Secondary Escalation**: Lead Architect
- **External Liaison**: Statutory Agency Technical SPOC (AICTE / State Registry liaison)

## 5. Safe Containment (Fail-Closed)
- Do NOT flag external outage as applicant document deficiency.
- Trigger automatic circuit breaker on affected provider code:
  ```bash
  uv run workbench provider set-circuit-breaker --provider AICTE_HISTORICAL --state OPEN
  ```
- Downstream evaluators will mark verification as `SOURCE_UNAVAILABLE` and create a single prioritized `manual_tasks` row for human officer review.

## 6. Diagnostic Steps
1. Verify if the outage is external or an egress/VPC NAT gateway issue:
   ```bash
   uv run workbench connector test-egress --provider AICTE_HISTORICAL
   ```
2. Inspect upstream rate-limit headers (`Retry-After`, `X-RateLimit-Remaining`).
3. Check certificate expiry on upstream TLS endpoints:
   ```bash
   uv run workbench connector check-ssl --provider AICTE_HISTORICAL
   ```

## 7. Recovery Commands & Mitigation
1. Back off polling intervals dynamically:
   ```bash
   uv run workbench provider set-rate-limit --provider AICTE_HISTORICAL --rpm 30
   ```
2. If outage exceeds SLA (> 2 hours), escalate pending cases to authorized manual review tasks:
   ```bash
   uv run workbench tasks escalate-source-outage --provider AICTE_HISTORICAL --age-hours 2
   ```
3. Once upstream confirms service restoration, reset circuit breaker and resume queue:
   ```bash
   uv run workbench provider set-circuit-breaker --provider AICTE_HISTORICAL --state CLOSED
   uv run workbench operations retry --failed-type SOURCE_UNAVAILABLE
   ```

## 8. Post-Recovery Verification
- Verify successful probe response:
  ```bash
  uv run workbench connector probe --provider AICTE_HISTORICAL
  ```
- Confirm `manual_tasks` transition to resolved upon officer manual confirmation.

## 9. Actions Requiring Policy / Security Sign-Off
- Disabling an external provider check permanently for an active evaluation cycle.
- Modifying statutory verification threshold rules.
