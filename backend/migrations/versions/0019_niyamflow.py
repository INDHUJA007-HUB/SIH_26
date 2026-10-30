"""Approval cases, continuing obligations and EVC planning with scoped access."""

from pathlib import Path

from alembic import op

revision = "0019"
down_revision = "0018"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute((Path(__file__).parents[1] / "sql/niyamflow_0019.sql").read_text())


def downgrade() -> None:
    raise RuntimeError("Export approval history before a reviewed forward-only rollback")
