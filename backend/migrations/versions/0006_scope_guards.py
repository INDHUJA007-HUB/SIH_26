"""Enforce administrative jurisdiction and intake states within the security kernel."""

from pathlib import Path

from alembic import op

revision = "0006_scope_guards"
down_revision = "0005_operations"
branch_labels = None
depends_on = None


def upgrade() -> None:
    source = Path(__file__).resolve().parents[1] / "sql" / "scope_guards.sql"
    with op.get_bind().connection.driver_connection.cursor() as cursor:
        cursor.execute(source.read_text(encoding="utf-8"))


def downgrade() -> None:
    raise RuntimeError("Security scope changes require a reviewed forward migration")
