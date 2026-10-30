"""Recheck persisted deadline generations before generating in-app alerts."""

from typing import Any

from sqlalchemy import select
from temporalio import activity

from workbench.adapters import tables as t
from workbench.adapters.niyam_service import NiyamService
from workbench.platform.config import Settings
from workbench.platform.runtime_roles import build_runtime_engine


def run(event_id: str, key: str | None = None) -> dict[str, Any]:
    engine = build_runtime_engine(Settings().worker_database_url.get_secret_value(), "wb_worker")
    try:
        with engine.begin() as conn:
            data = conn.execute(
                select(t.outbox.c.payload).where(t.outbox.c.id == event_id)
            ).scalar_one()
            service = NiyamService(conn)
            args = data["resource_id"], data["resource_kind"], data["generation"]
            return service.fire_deadline(*args, key) if key else service.deadline_plan(*args)
    finally:
        engine.dispose()


@activity.defn
def load_niyam_deadline(event_id: str) -> dict[str, Any]:
    return run(event_id)


@activity.defn
def fire_niyam_deadline(data: dict[str, str]) -> dict[str, Any]:
    return run(data["event_id"], data["key"])
