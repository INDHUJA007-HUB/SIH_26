"""Rebuild response facts from admitted object versions and evaluate in one commit."""

import hashlib
import json
from typing import Any
from uuid import uuid4

from sqlalchemy import select, text
from temporalio import activity

from workbench.adapters import tables as t
from workbench.adapters.evaluation_service import EvaluationService
from workbench.adapters.extraction_service import ExtractionService
from workbench.adapters.object_storage import ObjectStorage
from workbench.adapters.rectification_application_service import RectificationService
from workbench.platform.config import Settings
from workbench.platform.runtime_roles import build_runtime_engine


@activity.defn
def reassess_response(event_id: str) -> dict[str, Any]:
    settings = Settings()
    engine = build_runtime_engine(settings.worker_database_url.get_secret_value(), "wb_worker")
    try:
        with engine.begin() as conn:
            event = conn.execute(select(t.outbox).where(t.outbox.c.id == event_id)).mappings().one()
            response = (
                conn.execute(
                    select(t.rectification_responses)
                    .where(
                        t.rectification_responses.c.id == event["payload"]["response_id"],
                    )
                    .with_for_update()
                )
                .mappings()
                .one()
            )
            if response["reassessment_run_id"]:
                return {"run_id": response["reassessment_run_id"], "replayed": True}
            app = (
                conn.execute(
                    select(t.applications)
                    .where(
                        t.applications.c.id == response["application_id"],
                    )
                    .with_for_update()
                )
                .mappings()
                .one()
            )
            if app["revision"] != response["application_revision"]:
                raise ValueError("Response revision is stale; supervised reassessment required")
            baseline = (
                conn.execute(
                    select(t.evaluation_runs)
                    .where(
                        t.evaluation_runs.c.application_id == app["id"],
                        t.evaluation_runs.c.institution_id == app["institution_id"],
                    )
                    .order_by(t.evaluation_runs.c.created_at.desc())
                    .limit(1)
                )
                .mappings()
                .first()
            )
            if baseline is None:
                raise ValueError("Baseline evaluation required")
            extraction = ExtractionService(engine)
            storage = ObjectStorage(settings)
            for evidence_id in response["response_manifest"]["evidence_replacements"].values():
                ev = (
                    conn.execute(select(t.evidence).where(t.evidence.c.id == evidence_id))
                    .mappings()
                    .one()
                )
                if ev["status"] != "ACCEPTED" or ev["application_id"] != app["id"]:
                    raise ValueError("Replacement is not admitted application evidence")
                if ev["media_type"] != "application/pdf":
                    continue  # Unsupported extraction remains unknown; never invent a field.
                stream = storage.read(ev["clean_key"], ev["clean_version"], storage.clean)
                try:
                    content = stream.read(settings.max_upload_bytes + 1)
                finally:
                    stream.close()
                if (
                    len(content) > settings.max_upload_bytes
                    or hashlib.sha256(content).hexdigest() != ev["sha256"]
                ):
                    raise ValueError("Stored evidence hash mismatch")
                extraction.run_pipeline(
                    app["institution_id"], app["id"], evidence_id, content, conn=conn
                )
            extraction._freeze_fact_set(conn, app["institution_id"], app["id"])
            run = EvaluationService(engine).run_evaluation(
                app["institution_id"],
                app["id"],
                baseline["evaluation_as_of"],
                conn=conn,
            )
            result = RectificationService(engine).reassess_and_diff(
                institution_id=app["institution_id"],
                application_id=app["id"],
                response_id=response["id"],
                baseline_run_id=baseline["id"],
                reassessed_findings=[],
                new_run_id=run["run_id"],
                conn=conn,
            )
            conn.execute(
                text(
                    "SELECT wb.append_audit(:id,:inst,:app,:kind,CAST(:payload AS jsonb),:request)"
                ),
                {
                    "id": str(uuid4()),
                    "inst": app["institution_id"],
                    "app": app["id"],
                    "kind": "RectificationReassessed",
                    "payload": json.dumps({"run_id": run["run_id"], "response_id": response["id"]}),
                    "request": event_id,
                },
            )
            return {"run_id": run["run_id"], "diff_id": result["id"]}
    finally:
        engine.dispose()
