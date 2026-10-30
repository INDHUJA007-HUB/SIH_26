"""Limit draft-policy visibility and index tenant/delegation history lookups."""

from alembic import op

revision = "0023"
down_revision = "0022"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
      DROP POLICY packs_read ON approval_process_packs;
      CREATE POLICY packs_read ON approval_process_packs FOR SELECT TO wb_app USING(
       wb.actor_id() IS NOT NULL AND (state='PUBLISHED' OR author_id=wb.actor_id()
       OR (wb.elevated() AND wb.has_role('rule_approver'))));
      CREATE INDEX niyam_grant_actor_scope ON approval_access_grants(actor_id,role,region,application_id)
       WHERE revoked_at IS NULL;
      CREATE INDEX niyam_case_owner ON approval_cases(institution_id,application_id);
      CREATE INDEX niyam_obligation_owner ON approval_obligations(institution_id,application_id,kind);
      CREATE INDEX niyam_history_case ON approval_history(case_id,created_at);
      CREATE INDEX niyam_history_owner ON approval_history(institution_id,application_id);
      CREATE INDEX niyam_appointment_case ON evc_appointments(case_id,state);
      CREATE INDEX niyam_alert_owner ON approval_deadline_alerts(institution_id,application_id,state);
      CREATE INDEX niyam_permit_slot ON approval_upload_permits(application_id,slot_id,expires_at)
       WHERE revoked_at IS NULL;
    """)


def downgrade() -> None:
    raise RuntimeError("Keep draft policies restricted; use a reviewed forward migration")
