"""Fail closed when a service is configured with a migration/owner credential."""

from sqlalchemy import text
from sqlalchemy.engine import Engine

from workbench.platform.database import build_engine


def validate_runtime_role(engine: Engine, group: str) -> None:
    with engine.connect() as connection:
        valid = connection.scalar(
            text(
                "SELECT NOT rolsuper AND NOT rolbypassrls AND NOT rolcreaterole "
                "AND pg_has_role(current_user,:group,'MEMBER') "
                "AND NOT pg_has_role(current_user,'wb_security_owner','MEMBER') "
                "AND NOT EXISTS (SELECT 1 FROM pg_class c WHERE "
                "c.relname='applications' AND c.relowner=r.oid) "
                "FROM pg_roles r WHERE rolname=current_user"
            ),
            {"group": group},
        )
        if valid is not True:
            raise RuntimeError("Runtime database credential exceeds its assigned role")


def build_runtime_engine(url: str, group: str) -> Engine:
    engine = build_engine(url)
    try:
        validate_runtime_role(engine, group)
        return engine
    except Exception:
        engine.dispose()
        raise
