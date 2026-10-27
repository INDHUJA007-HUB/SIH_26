"""Synthetic foundation tables only; no production application schema."""

import sqlalchemy as sa
from alembic import op

revision = "0001_foundation"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "foundation_institutions",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("display_name", sa.String(200), nullable=False),
        sa.Column("synthetic", sa.Boolean(), nullable=False),
        sa.CheckConstraint("synthetic = true", name="ck_foundation_synthetic_only"),
    )
    op.create_table(
        "seed_rule_candidates",
        sa.Column("rule_id", sa.String(100), primary_key=True),
        sa.Column("publication_state", sa.String(30), nullable=False),
        sa.Column("production_enabled", sa.Boolean(), nullable=False),
        sa.Column("adverse_action_allowed", sa.Boolean(), nullable=False),
        sa.Column("source_sha256", sa.String(64), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column(
            "imported_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.CheckConstraint("publication_state = 'DRAFT'", name="ck_seed_draft_only"),
        sa.CheckConstraint("production_enabled = false", name="ck_seed_no_production"),
        sa.CheckConstraint("adverse_action_allowed = false", name="ck_seed_no_adverse"),
    )


def downgrade() -> None:
    op.drop_table("seed_rule_candidates")
    op.drop_table("foundation_institutions")
