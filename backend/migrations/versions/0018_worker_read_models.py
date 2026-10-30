"""Input privileges for lifecycle and media workers."""

from alembic import op

revision = "0018"
down_revision = "0017"
branch_labels = None
depends_on = None

INPUTS = (
    "applications",
    "application_revisions",
    "evidence_slots",
    "evidence_versions",
    "evidence_derivatives",
)


def upgrade() -> None:
    for table in INPUTS:
        op.execute(f"GRANT SELECT ON {table} TO wb_worker")
        op.execute(
            f"CREATE POLICY lifecycle_worker_read ON {table} FOR SELECT TO wb_worker USING (true)"
        )
    op.execute("GRANT UPDATE(revision) ON applications TO wb_worker")
    op.execute(
        "CREATE POLICY lifecycle_worker_lock ON applications FOR UPDATE TO wb_worker USING (true) WITH CHECK (true)"
    )
    op.execute("GRANT INSERT ON evidence_derivatives TO wb_worker")
    op.execute(
        "CREATE POLICY media_worker_derivative_insert ON evidence_derivatives FOR INSERT TO wb_worker WITH CHECK (true)"
    )
    op.execute(
        "CREATE POLICY supervisor_case_read ON applications FOR SELECT TO wb_app USING (wb.elevated() AND wb.has_role('supervisor'))"
    )
    op.execute(
        "CREATE POLICY supervisor_case_command ON applications FOR UPDATE TO wb_app USING (wb.elevated() AND wb.has_role('supervisor')) WITH CHECK (wb.elevated() AND wb.has_role('supervisor'))"
    )


def downgrade() -> None:
    op.execute("DROP POLICY supervisor_case_command ON applications")
    op.execute("DROP POLICY supervisor_case_read ON applications")
    op.execute("DROP POLICY media_worker_derivative_insert ON evidence_derivatives")
    op.execute("REVOKE INSERT ON evidence_derivatives FROM wb_worker")
    op.execute("DROP POLICY lifecycle_worker_lock ON applications")
    op.execute("REVOKE UPDATE(revision) ON applications FROM wb_worker")
    for table in INPUTS:
        op.execute(f"DROP POLICY lifecycle_worker_read ON {table}")
        op.execute(f"REVOKE SELECT ON {table} FROM wb_worker")  # noqa: S608 -- fixed migration identifiers
