# Operational Runbook 13: Secondary Region Disaster Recovery & Failover

## 1. Overview & Context
Procedures for failing over the AICTE Workbench from primary region (ap-south-1 Mumbai) to secondary region (ap-south-2 Hyderabad) in the event of an AWS complete regional outage.

## 2. Recovery Objectives (Section 12.2)
- **Target Regional Objectives**: RPO $\le 15\text{ minutes}$, RTO $\le 4\text{ hours}$.
- **Replication Architecture**:
  - AWS Backup cross-region RDS snapshot copies (every 4 hours).
  - S3 Cross-Region Replication (CRR) on `clean`, `reports`, and `audit_vault` buckets with KMS re-encryption.
  - Route 53 DNS Failover with health-checked alias records.

## 3. Owner & Escalation Path
- **Disaster Recovery Commander**: VP of Engineering / Lead Architect
- **Technical Leads**: Platform Lead, DBA, Security Lead
- **Executive Sign-off**: AICTE Member Secretary & CISO

## 4. Execution Sequence

### Phase 1: Failover Declaration & Assessment
1. Confirm primary region loss with AWS Health Dashboard.
2. Formally declare disaster state (SEV-0).

### Phase 2: Secondary Infrastructure Activation
1. Navigate to secondary region Terraform workspace:
   ```bash
   cd infra/terraform/environments/production
   terraform workspace select production-hyderabad
   terraform apply -var="aws_region=ap-south-2" -auto-approve
   ```
2. Restore latest cross-region RDS snapshots for domain DB and Temporal:
   ```bash
   aws rds restore-db-instance-from-db-snapshot \
     --region ap-south-2 \
     --db-instance-identifier prod-aicte-domain-db-dr \
     --db-snapshot-identifier <latest_cross_region_snapshot_arn>
   ```

### Phase 3: S3 & Key Recovery
1. Verify S3 secondary replica buckets (`clean`, `reports`, `audit_vault`).
2. Verify secondary KMS key alias `alias/production-aicte-app-dr` access.

### Phase 4: Reconcile Data & State
1. Execute recovery drill in secondary region:
   ```bash
   uv run python backend/tools/recovery_drill.py
   ```
2. Identify missing transactions between last snapshot and failure time; alert institutions whose submissions fell into the recovery gap window.

### Phase 5: DNS Cutover
1. Update Route 53 DNS records to point to secondary ALB:
   ```bash
   aws route53 change-resource-record-sets --hosted-zone-id <zone_id> --change-batch file://dns_failover.json
   ```
2. Monitor DNS propagation and health checks.

## 5. Post-Recovery Verification
- Perform smoke test on secondary edge:
  ```bash
  curl -I https://workbench.aicte-india.org/api/v1/health
  ```
- Run full acceptance suite against DR environment.

## 6. Actions Requiring Policy / Security Sign-Off
- Authorizing production traffic switch to secondary region.
- Deciding on whether to extend statutory deadlines for affected applicants.
