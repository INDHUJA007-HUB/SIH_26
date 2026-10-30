"""Scoped access to intake slots and deadline outbox handoffs for delegates."""

from alembic import op

revision = "0021"
down_revision = "0020"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
      CREATE POLICY niyam_slot_read ON evidence_slots FOR SELECT TO wb_app USING(
       (wb.elevated() AND wb.has_role('supervisor') AND wb.manages(institution_id)) OR
       EXISTS(SELECT FROM applications a WHERE a.id=application_id AND (
        wb.niyam_role('REGIONAL',a.jurisdiction,a.id) OR wb.niyam_role('BUREAU',a.jurisdiction,a.id)
        OR wb.niyam_role('COMMITTEE',a.jurisdiction,a.id) OR wb.niyam_role('AUTHORITY',a.jurisdiction,a.id))));
      CREATE POLICY niyam_deadline_intent ON outbox_events FOR INSERT TO wb_app WITH CHECK(
       event_type='NiyamDeadlineScheduled' AND (
        (payload->>'resource_kind'='CASE' AND EXISTS(SELECT FROM approval_cases c
         WHERE c.id=payload->>'resource_id' AND c.institution_id=outbox_events.institution_id
         AND c.application_id IS NOT DISTINCT FROM outbox_events.application_id
         AND c.generation::text=payload->>'generation')) OR
        (payload->>'resource_kind'='OBLIGATION' AND EXISTS(SELECT FROM approval_obligations o
         WHERE o.id=payload->>'resource_id' AND o.institution_id=outbox_events.institution_id
         AND o.application_id IS NOT DISTINCT FROM outbox_events.application_id
         AND o.generation::text=payload->>'generation'))));
    """)


def downgrade() -> None:
    op.execute("DROP POLICY niyam_deadline_intent ON outbox_events")
    op.execute("DROP POLICY niyam_slot_read ON evidence_slots")
