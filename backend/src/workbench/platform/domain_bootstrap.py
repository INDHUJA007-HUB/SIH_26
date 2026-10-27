"""Explicit local role provisioning and repeatable synthetic identity seed."""

import json
import secrets
from datetime import UTC, datetime
from pathlib import Path
from uuid import NAMESPACE_URL, uuid5

import psycopg
from dotenv import dotenv_values
from psycopg import sql
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.engine import make_url

from workbench.adapters import tables as t
from workbench.platform.config import PROJECT_ROOT, Settings
from workbench.platform.database import build_engine

ROLE_CONFIG = {
    "APP": ("workbench_api", "wb_app"),
    "DELIVERY": ("workbench_delivery", "wb_delivery"),
    "RELAY": ("workbench_relay", "wb_relay"),
    "SCAN": ("workbench_scanner", "wb_scanner"),
    "WORKER": ("workbench_worker", "wb_worker"),
}


def ensure_local_credentials(root: Path = PROJECT_ROOT) -> None:
    path = root / ".env"
    values = dotenv_values(path)
    source_url = make_url(str(values["WB_DATABASE_URL"]))
    additions = []
    for label, (login, _) in ROLE_CONFIG.items():
        password_key = f"{label}_DATABASE_PASSWORD"
        password = values.get(password_key) or secrets.token_urlsafe(32)
        if not values.get(password_key):
            additions.append(f"{password_key}={password}")
        url_key = f"WB_{label}_DATABASE_URL"
        if not values.get(url_key):
            additions.append(
                f"{url_key}="
                + source_url.set(username=login, password=password).render_as_string(
                    hide_password=False
                )
            )
    if additions:
        with path.open("a", encoding="utf-8") as destination:
            destination.write("\n" + "\n".join(additions) + "\n")


def configure_roles(settings: Settings) -> None:
    if settings.environment not in {"local", "test", "integration"}:
        raise ValueError("Local role bootstrap is not a production provisioning mechanism")
    source = make_url(settings.database_url.get_secret_value())
    if source.host not in {"127.0.0.1", "localhost", "postgres"}:
        raise ValueError("Local role bootstrap refuses a remote database")
    values = dotenv_values(PROJECT_ROOT / ".env")
    import os

    with psycopg.connect(
        source.set(drivername="postgresql").render_as_string(hide_password=False)
    ) as connection:
        for label, (login, group) in ROLE_CONFIG.items():
            password = os.environ.get(f"{label}_DATABASE_PASSWORD") or values.get(
                f"{label}_DATABASE_PASSWORD"
            )
            if not password:
                raise ValueError(f"Missing generated credential for {label}")
            with connection.cursor() as cursor:
                cursor.execute("SELECT 1 FROM pg_roles WHERE rolname=%s", (login,))
                if cursor.fetchone() is None:
                    cursor.execute(
                        sql.SQL(
                            "CREATE ROLE {} LOGIN NOSUPERUSER NOCREATEDB "
                            "NOCREATEROLE NOINHERIT NOBYPASSRLS"
                        ).format(sql.Identifier(login))
                    )
                cursor.execute(
                    sql.SQL("ALTER ROLE {} INHERIT PASSWORD {}").format(
                        sql.Identifier(login), sql.Literal(password)
                    )
                )
                cursor.execute(
                    sql.SQL("GRANT {} TO {}").format(sql.Identifier(group), sql.Identifier(login))
                )


def seed_domain(settings: Settings) -> dict[str, int]:
    if settings.environment not in {"local", "test", "integration"}:
        raise ValueError("Synthetic identity seed is restricted to development")
    engine = build_engine(settings.database_url.get_secret_value())
    fixtures = json.loads((PROJECT_ROOT / "backend/fixtures/foundation.json").read_text())
    identities = [
        ("1", "institution_editor", "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa"),
        ("2", "institution_editor", "bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb"),
        ("3", "officer", None),
        ("4", "auditor", None),
        ("5", "supervisor", None),
        ("6", "identity_admin", None),
        ("7", "rule_author", None),
        ("8", "rule_approver", None),
    ]
    with engine.begin() as connection:
        for institution in fixtures["institutions"]:
            connection.execute(
                pg_insert(t.institutions)
                .values(
                    id=institution["id"],
                    name=institution["display_name"],
                    jurisdiction="TN",
                    synthetic=True,
                )
                .on_conflict_do_nothing()
            )
        for issuer in {"urn:sih:local-fixture", "http://127.0.0.1:8081/realms/sih-local"}:
            for digit, role, institution_id in identities:
                subject = f"{digit * 8}-{digit * 4}-4{digit * 3}-8{digit * 3}-{digit * 12}"
                actor_id = str(uuid5(NAMESPACE_URL, issuer + "|" + subject))
                connection.execute(
                    pg_insert(t.actors)
                    .values(
                        id=actor_id,
                        issuer=issuer,
                        subject=subject,
                        person_id=subject,
                        disabled=False,
                        valid_after=datetime(2000, 1, 1, tzinfo=UTC),
                    )
                    .on_conflict_do_nothing()
                )
                connection.execute(
                    pg_insert(t.memberships)
                    .values(
                        id=str(uuid5(NAMESPACE_URL, actor_id + "|" + role)),
                        actor_id=actor_id,
                        institution_id=institution_id,
                        role=role,
                        jurisdiction="TN",
                        granted_by="LOCAL_SYNTHETIC_BOOTSTRAP",
                    )
                    .on_conflict_do_nothing()
                )
    engine.dispose()
    return {"institutions": 2, "actor_bindings": 16, "production_rules": 0}
