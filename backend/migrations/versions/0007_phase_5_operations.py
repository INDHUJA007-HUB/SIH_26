"""Phase 5 durable operations tracking and concurrency controls."""

import sqlalchemy as sa
from alembic import op

revision = "0007_phase_5_operations"
down_revision = "0006_scope_guards"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "operations",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("institution_id", sa.String(36), nullable=False),
        sa.Column("application_id", sa.String(36)),
        sa.Column("operation_type", sa.String(80), nullable=False),
        sa.Column("task_queue", sa.String(60), nullable=False),
        sa.Column("status", sa.String(30), nullable=False),
        sa.Column("stable_key", sa.String(200), nullable=False),
        sa.Column("workflow_id", sa.String(120)),
        sa.Column("input_ref", sa.JSON(), nullable=False),
        sa.Column("result", sa.JSON()),
        sa.Column("error_code", sa.String(80)),
        sa.Column("error_message", sa.Text()),
        sa.Column("attempts", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("paused", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.ForeignKeyConstraint(
            ["institution_id", "application_id"],
            ["applications.institution_id", "applications.id"],
            name="fk_operation_owner",
        ),
        sa.ForeignKeyConstraint(
            ["institution_id"],
            ["institutions.id"],
            name="fk_operation_institution",
        ),
        sa.UniqueConstraint(
            "institution_id",
            "operation_type",
            "stable_key",
            name="uq_operation_stable_key",
        ),
    )

    op.create_index(
        "ix_operations_institution_status",
        "operations",
        ["institution_id", "status"],
    )
    op.create_index(
        "ix_operations_status_queue",
        "operations",
        ["status", "task_queue"],
    )
    op.create_index(
        "ix_operations_owner_time",
        "operations",
        ["institution_id", "created_at", "id"],
    )

    # Security kernel and RLS
    op.execute("ALTER TABLE operations ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE operations FORCE ROW LEVEL SECURITY")

    elevated_check = "(wb.elevated() AND (wb.has_role('supervisor') OR wb.has_role('officer')))"

    op.execute(
        f"CREATE POLICY operation_read ON operations FOR SELECT TO wb_app "
        f"USING (wb.can_access(institution_id, application_id, false) "
        f"OR wb.manages(institution_id) OR {elevated_check})"
    )
    op.execute(
        f"CREATE POLICY operation_write ON operations FOR ALL TO wb_app "
        f"USING (wb.can_access(institution_id, application_id, true) OR {elevated_check}) "
        f"WITH CHECK (wb.can_access(institution_id, application_id, true) OR {elevated_check})"
    )
    op.execute(
        "CREATE POLICY worker_operations ON operations FOR ALL TO wb_worker, wb_scanner, wb_relay "
        "USING (true) WITH CHECK (true)"
    )
    op.execute(
        "GRANT SELECT, INSERT, UPDATE ON operations TO "
        "wb_app, wb_worker, wb_scanner, wb_relay, wb_security_owner"
    )


def downgrade() -> None:
    raise RuntimeError("Operational security changes require a reviewed forward migration")
