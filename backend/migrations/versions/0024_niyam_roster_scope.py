"""Regional roster visibility must not depend on an unscoped role label."""

from alembic import op

revision = "0024"
down_revision = "0023"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
      DROP POLICY roster_read ON evc_rosters;
      CREATE POLICY roster_read ON evc_rosters FOR SELECT TO wb_app USING(wb.elevated() AND (
       EXISTS(SELECT FROM memberships m WHERE m.actor_id=wb.actor_id()
        AND m.role IN ('officer','supervisor') AND m.jurisdiction=region AND m.revoked_at IS NULL
        AND (m.expires_at IS NULL OR m.expires_at>statement_timestamp()))
       OR wb.niyam_role('REGIONAL',region,NULL) OR wb.niyam_role('BUREAU',region,NULL)));
    """)


def downgrade() -> None:
    raise RuntimeError("Do not restore unscoped roster visibility")
