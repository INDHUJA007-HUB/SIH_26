"""Phase 10 tasks, alerts, versioned durable timers, notifications, and audit checkpoints.

Revision ID: 0012_phase_10_alerts_audit
Revises: 0011_phase_9_rectification
Create Date: 2026-10-28
"""

import sqlalchemy as sa
from alembic import op

revision = "0012_phase_10_alerts_audit"
down_revision = "0011_phase_9_rectification"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 1. alerts (separated security and compliance alert triggers with semantic dedup keys)
    op.create_table(
        "alerts",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("institution_id", sa.String(36), nullable=False),
        sa.Column("application_id", sa.String(36)),
        sa.Column("category", sa.String(50), nullable=False),
        sa.Column("trigger_type", sa.String(50), nullable=False),
        sa.Column("dedup_key", sa.String(255), nullable=False),
        sa.Column("severity", sa.String(20), nullable=False),
        sa.Column("title", sa.String(200), nullable=False),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column("status", sa.String(30), nullable=False, server_default="OPEN"),
        sa.Column("details", sa.JSON()),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column("acknowledged_at", sa.DateTime(timezone=True)),
        sa.Column("resolved_at", sa.DateTime(timezone=True)),
        sa.Column("acknowledged_by", sa.String(36)),
        sa.ForeignKeyConstraint(
            ["institution_id"],
            ["institutions.id"],
            name="fk_alerts_institution",
        ),
        sa.ForeignKeyConstraint(
            ["application_id"],
            ["applications.id"],
            name="fk_alerts_application",
        ),
    )

    # 2. lifecycle_tasks (semantic tasks with state machine:
    #    OPEN, IN_PROGRESS, RESOLVED, CANCELLED, ESCALATED)
    op.create_table(
        "lifecycle_tasks",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("institution_id", sa.String(36), nullable=False),
        sa.Column("application_id", sa.String(36)),
        sa.Column("task_type", sa.String(50), nullable=False),
        sa.Column("dedup_key", sa.String(255), nullable=False),
        sa.Column("state", sa.String(30), nullable=False, server_default="OPEN"),
        sa.Column("assigned_to", sa.String(36)),
        sa.Column("details", sa.JSON()),
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
        sa.Column("resolved_at", sa.DateTime(timezone=True)),
        sa.ForeignKeyConstraint(
            ["institution_id"],
            ["institutions.id"],
            name="fk_lifecycle_tasks_institution",
        ),
        sa.ForeignKeyConstraint(
            ["application_id"],
            ["applications.id"],
            name="fk_lifecycle_tasks_application",
        ),
    )

    # 3. durable_timers (versioned durable timers:
    #    replacing evidence cancels older generation reminders)
    op.create_table(
        "durable_timers",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("institution_id", sa.String(36), nullable=False),
        sa.Column("application_id", sa.String(36), nullable=False),
        sa.Column("slot_id", sa.String(36)),
        sa.Column("timer_type", sa.String(50), nullable=False),
        sa.Column("generation", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("deadline", sa.DateTime(timezone=True), nullable=False),
        sa.Column("status", sa.String(30), nullable=False, server_default="SCHEDULED"),
        sa.Column("details", sa.JSON()),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column("cancelled_at", sa.DateTime(timezone=True)),
        sa.Column("fired_at", sa.DateTime(timezone=True)),
        sa.ForeignKeyConstraint(
            ["institution_id"],
            ["institutions.id"],
            name="fk_durable_timers_institution",
        ),
        sa.ForeignKeyConstraint(
            ["application_id"],
            ["applications.id"],
            name="fk_durable_timers_application",
        ),
    )

    # 4. notifications (in-app and Mailpit deliveries: queued, sent, failed, unknown, acknowledged)
    op.create_table(
        "notifications",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("institution_id", sa.String(36), nullable=False),
        sa.Column("application_id", sa.String(36)),
        sa.Column("alert_id", sa.String(36)),
        sa.Column("task_id", sa.String(36)),
        sa.Column("recipient", sa.String(255), nullable=False),
        sa.Column("channel", sa.String(20), nullable=False),
        sa.Column("status", sa.String(30), nullable=False, server_default="QUEUED"),
        sa.Column("provider_reference", sa.String(100)),
        sa.Column("subject", sa.String(250)),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("retry_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("retry_history", sa.JSON()),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column("sent_at", sa.DateTime(timezone=True)),
        sa.Column("acknowledged_at", sa.DateTime(timezone=True)),
        sa.ForeignKeyConstraint(
            ["institution_id"],
            ["institutions.id"],
            name="fk_notifications_institution",
        ),
        sa.ForeignKeyConstraint(
            ["application_id"],
            ["applications.id"],
            name="fk_notifications_application",
        ),
        sa.ForeignKeyConstraint(
            ["alert_id"],
            ["alerts.id"],
            name="fk_notifications_alert",
        ),
        sa.ForeignKeyConstraint(
            ["task_id"],
            ["lifecycle_tasks.id"],
            name="fk_notifications_task",
        ),
    )

    # 5. audit_checkpoints (cryptographic audit hash checkpoints and
    #    exports under scoped auditor permission)
    op.create_table(
        "audit_checkpoints",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("institution_id", sa.String(36), nullable=False),
        sa.Column("application_id", sa.String(36)),
        sa.Column("auditor_id", sa.String(36), nullable=False),
        sa.Column("stream", sa.String(80), nullable=False),
        sa.Column("start_sequence", sa.BigInteger(), nullable=False),
        sa.Column("end_sequence", sa.BigInteger(), nullable=False),
        sa.Column("event_count", sa.Integer(), nullable=False),
        sa.Column("checkpoint_hash", sa.String(64), nullable=False),
        sa.Column("archive_lag_seconds", sa.Float(), nullable=False, server_default="0"),
        sa.Column(
            "integrity_status",
            sa.String(20),
            nullable=False,
            server_default="VERIFIED",
        ),
        sa.Column("manifest", sa.JSON(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.ForeignKeyConstraint(
            ["institution_id"],
            ["institutions.id"],
            name="fk_audit_checkpoints_institution",
        ),
        sa.ForeignKeyConstraint(
            ["application_id"],
            ["applications.id"],
            name="fk_audit_checkpoints_application",
        ),
        sa.ForeignKeyConstraint(
            ["auditor_id"],
            ["actor_identities.id"],
            name="fk_audit_checkpoints_auditor",
        ),
    )

    # Secondary indexes
    op.create_index("ix_alerts_dedup_status", "alerts", ["dedup_key", "status"])
    op.create_index("ix_alerts_category_status", "alerts", ["category", "status"])
    op.create_index("ix_lifecycle_tasks_dedup", "lifecycle_tasks", ["dedup_key"])
    op.create_index(
        "ix_durable_timers_slot_gen",
        "durable_timers",
        ["slot_id", "generation"],
    )
    op.create_index("ix_notifications_status", "notifications", ["status"])
    op.create_index("ix_audit_checkpoints_app", "audit_checkpoints", ["application_id"])

    # RLS Policies and owner indexes
    p10_tables = [
        "alerts",
        "lifecycle_tasks",
        "durable_timers",
        "notifications",
        "audit_checkpoints",
    ]
    elevated_check = "(wb.elevated() AND (wb.has_role('supervisor') OR wb.has_role('auditor')))"
    can_read = (
        f"(wb.can_access(institution_id, application_id, false) OR wb.manages(institution_id) "
        f"OR {elevated_check})"
    )
    can_write = (
        f"(wb.can_access(institution_id, application_id, true) OR wb.manages(institution_id) "
        f"OR {elevated_check})"
    )

    for tbl in p10_tables:
        op.create_index(f"ix_{tbl}_owner_time", tbl, ["institution_id", "created_at", "id"])
        op.execute(f"ALTER TABLE {tbl} ENABLE ROW LEVEL SECURITY")
        op.execute(f"ALTER TABLE {tbl} FORCE ROW LEVEL SECURITY")
        op.execute(f"CREATE POLICY {tbl}_read ON {tbl} FOR SELECT TO wb_app USING ({can_read})")
        op.execute(
            f"CREATE POLICY {tbl}_write ON {tbl} FOR ALL TO wb_app "
            f"USING ({can_write}) "
            f"WITH CHECK ({can_write})"
        )
        op.execute(
            f"CREATE POLICY worker_{tbl} ON {tbl} FOR ALL TO wb_worker, wb_scanner, wb_relay "
            "USING (true) WITH CHECK (true)"
        )
        op.execute(
            f"GRANT SELECT, INSERT, UPDATE, DELETE ON {tbl} TO "
            "wb_app, wb_worker, wb_scanner, wb_relay, wb_security_owner"
        )


def downgrade() -> None:
    raise RuntimeError("Operational security changes require a reviewed forward migration")
