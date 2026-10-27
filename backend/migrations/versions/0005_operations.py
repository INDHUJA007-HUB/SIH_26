"""Bounded reconciliation checkpoints and storage lookup indexes."""

import sqlalchemy as sa
from alembic import op

revision = "0005_operations"
down_revision = "0004_identity_guards"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "reconciliation_cursors",
        sa.Column("name", sa.String(40), primary_key=True),
        sa.Column("position", sa.JSON(), nullable=False),
    )
    op.execute("ALTER TABLE reconciliation_cursors ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE reconciliation_cursors FORCE ROW LEVEL SECURITY")
    op.execute(
        "CREATE POLICY reconciliation_scanner ON reconciliation_cursors FOR ALL "
        "TO wb_scanner USING(true) WITH CHECK(true)"
    )
    op.execute("GRANT SELECT,INSERT,UPDATE ON reconciliation_cursors TO wb_scanner")
    op.execute(
        "CREATE INDEX ix_evidence_clean_object ON evidence_versions(clean_key,clean_version)"
    )
    op.execute(
        "CREATE INDEX ix_derivative_object ON evidence_derivatives(object_key,object_version)"
    )


def downgrade() -> None:
    raise RuntimeError("Operational security changes require a reviewed forward migration")
