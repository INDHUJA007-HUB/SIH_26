"""Enforce report audience isolation and serialize response submissions."""

from alembic import op

revision = "0017"
down_revision = "0016_phase_15_ops_retention"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # RESTRICTIVE policies apply in addition to existing tenant policies.
    op.execute("""
        CREATE POLICY report_audience_read ON validation_reports AS RESTRICTIVE
        FOR SELECT TO wb_app USING (
            audience = 'APPLICANT' OR
            (wb.elevated() AND (wb.has_role('officer') OR wb.has_role('supervisor')))
        )
    """)
    op.execute("""
        CREATE POLICY report_audience_insert ON validation_reports AS RESTRICTIVE
        FOR INSERT TO wb_app WITH CHECK (
            audience = 'APPLICANT' OR
            (wb.elevated() AND (wb.has_role('officer') OR wb.has_role('supervisor')))
        )
    """)
    op.create_unique_constraint(
        "uq_response_window_submission", "rectification_responses", ["window_id"]
    )
    op.execute("""
        CREATE UNIQUE INDEX uq_active_response_window ON response_windows(application_id)
        WHERE status = 'OPEN'
    """)


def downgrade() -> None:
    op.execute("DROP INDEX uq_active_response_window")
    op.drop_constraint("uq_response_window_submission", "rectification_responses", type_="unique")
    op.execute("DROP POLICY report_audience_insert ON validation_reports")
    op.execute("DROP POLICY report_audience_read ON validation_reports")
