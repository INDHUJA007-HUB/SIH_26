# Operational Runbook 08: Regulatory Rule Release Rollback & Supersession

## 1. Overview & Context
Handles urgent rollback or supersession of a published rule release (e.g. flawed DSL logic, judicial stay on a regulatory clause, or incorrect parameter table published by regulatory authorities).

## 2. Key Regulatory Principles
- **Published Releases are Immutable**: A published rule release CANNOT be deleted or modified in-place (enforced by database trigger `block_published_rule_release_mutation()`).
- **Supersession Model**: Rollback is achieved by publishing a new forward superseding release (e.g. restoring previous parameters) with dual control.
- **Historical Run Preservation**: Old runs evaluated under the flawed release remain historically intact with their original manifest hashes.

## 3. Symptoms & Triggering Alarms
- Regulatory Notification: Gazette amendment or judicial stay order received.
- Discrepancy Surge: Unintended mass potential deficiencies flagged on compliant institutions.

## 4. Owner & Escalation Path
- **Primary Owner**: Regulatory Rule Author & Approver (Dual Control)
- **Secondary Escalation**: Legal & Regulatory Policy Directorate
- **Technical Operator**: Lead Platform Engineer

## 5. Safe Rollback Procedure

### Step 1: Create Superseding Candidate
Create a new rule candidate restoring the previous canonical rule parameters:
```bash
uv run workbench rules create-candidate \
  --code "APH-ROLLBACK-RELEASE-2026B" \
  --effective-date "2026-10-28" \
  --from-release "rel-base-2026" \
  --reason "Judicial stay on Clause 4.1 bandwidth amendment"
```

### Step 2: Simulate Impact Diff
Run offline impact simulation to confirm that intended applications return to compliant status:
```bash
uv run workbench rules simulate --candidate-code "APH-ROLLBACK-RELEASE-2026B"
```

### Step 3: Dual-Control Approval & Publication
1. Independent Officer A gates review:
   ```bash
   uv run workbench rules gate-check --candidate-code "APH-ROLLBACK-RELEASE-2026B" --actor officer_a
   ```
2. Independent Supervisor B approves (must not be same person as Author):
   ```bash
   uv run workbench rules approve --candidate-code "APH-ROLLBACK-RELEASE-2026B" --actor supervisor_b
   ```
3. Publish release:
   ```bash
   uv run workbench rules publish --candidate-code "APH-ROLLBACK-RELEASE-2026B" --actor supervisor_b
   ```

### Step 4: Re-evaluate Active Open Cases
Re-evaluate pending applications affected by the flawed clause:
```bash
uv run workbench evaluation re-evaluate-cohort --cohort-id "PILOT-2026A" --rule-release "APH-ROLLBACK-RELEASE-2026B"
```

## 6. Post-Recovery Verification
- Verify historical run immutability:
  ```bash
  uv run pytest backend/tests/test_phase_12_rule_governance.py -k "test_old_run_replay_reproduces_output_hash"
  ```
- Confirm that new evaluation runs reflect the superseding rule release.

## 7. Actions Requiring Policy / Security Sign-Off
- Authorizing emergency expedited rule publication during an ongoing application window.
- Overriding the 4-eye dual control maker-checker requirement (forbidden by policy).
