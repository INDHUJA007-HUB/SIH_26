"""Phase 14 pilot onboarding and scope activation gates.

Revision ID: 0015_phase_14_pilot_scope
Revises: 0014_phase_12_rule_governance
Create Date: 2026-10-28
"""

import sqlalchemy as sa
from alembic import op

revision = "0015_phase_14_pilot_scope"
down_revision = "0014_phase_12_rule_governance"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "pilot_scopes",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("cohort_id", sa.String(100), nullable=False),
        sa.Column("institution_ids", sa.JSON(), nullable=False),
        sa.Column("enabled_rule_release_id", sa.String(100), nullable=True),
        sa.Column("provider_mode", sa.String(40), nullable=False, server_default="SIMULATED"),
        sa.Column(
            "outbound_notifications_enabled",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
        sa.Column(
            "advisory_mode_only", sa.Boolean(), nullable=False, server_default=sa.text("true")
        ),
        sa.Column("approval_officer_ids", sa.JSON(), nullable=False),
        sa.Column("activated_by", sa.String(36), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column("deactivated_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint("advisory_mode_only = true", name="ck_pilot_advisory_mode_only"),
    )

    op.create_index("ix_pilot_scopes_cohort", "pilot_scopes", ["cohort_id"])
    op.create_index("ix_pilot_scopes_active", "pilot_scopes", ["is_active"])

    conn = op.get_bind()
    conn.execute(
        sa.text("""
        GRANT SELECT, INSERT, UPDATE ON TABLE pilot_scopes TO wb_app, wb_worker, wb_security_owner;
    """)
    )


def downgrade() -> None:
    raise RuntimeError("Phase 14 schema downgrade is not permitted; forward roll only.")
