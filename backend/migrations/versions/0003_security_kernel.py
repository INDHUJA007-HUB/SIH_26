"""RLS, append-only history, immutable submissions, and least-privilege role groups."""

from pathlib import Path

from alembic import op

revision = "0003_security_kernel"
down_revision = "73ea0be4cdff"
branch_labels = None
depends_on = None


def upgrade() -> None:
    source = Path(__file__).resolve().parents[1] / "sql/phase_2_4_security.sql"
    with op.get_bind().connection.driver_connection.cursor() as cursor:
        cursor.execute(source.read_text(encoding="utf-8"))


def downgrade() -> None:
    raise RuntimeError("Security/history rollback requires a reviewed forward migration")
