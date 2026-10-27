"""Migrations use an explicit URL and never print credentials."""

from alembic import context

from workbench.adapters import tables  # noqa: F401 -- registers domain metadata
from workbench.platform.config import Settings
from workbench.platform.database import Base, build_engine

target_metadata = Base.metadata
settings = Settings()
url = settings.database_url.get_secret_value()
if not url:
    raise RuntimeError("WB_DATABASE_URL is required to run migrations")

if context.is_offline_mode():
    context.configure(url=url, target_metadata=target_metadata, literal_binds=True)
    with context.begin_transaction():
        context.run_migrations()
else:
    engine = build_engine(url)
    try:
        with engine.connect() as connection:
            context.configure(
                connection=connection, target_metadata=target_metadata, compare_type=True
            )
            with context.begin_transaction():
                context.run_migrations()
    finally:
        engine.dispose()
