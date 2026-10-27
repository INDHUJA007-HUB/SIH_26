"""Content-free Phase 2–4 service/isolation/query-plan verification evidence."""

import json
import shutil
import subprocess
from datetime import UTC, datetime

import httpx
from sqlalchemy import text

from workbench.adapters.audit_verifier import verify_stream
from workbench.platform.config import PROJECT_ROOT, Settings
from workbench.platform.database import build_engine
from workbench.tools import fixture_token

settings = Settings()
report = {"scope": "LOCAL_SYNTHETIC_PHASE_2_4", "checked_at": datetime.now(UTC).isoformat()}
with httpx.Client(timeout=10) as http:
    capability = http.get("http://127.0.0.1:8000/api/v1/capabilities").json()
    assert capability["release_scope"] == "PHASE_4_INTAKE"
    report["capabilities"] = capability
    me = http.get(
        "http://127.0.0.1:8000/api/v1/me",
        headers={"Authorization": "Bearer " + fixture_token(settings)},
    )
    assert me.status_code == 200
    report["persisted_identity"] = "PASS"
    query = http.get(
        "http://127.0.0.1:9090/api/v1/query",
        params={"query": 'up{job=~"workbench-(api|outbox|scan|reconciliation)"}'},
    ).json()["data"]["result"]
    assert len(query) == 4 and all(item["value"][1] == "1" for item in query)
    report["private_metrics_targets"] = {item["metric"]["job"]: "UP" for item in query}

engine = build_engine(settings.database_url.get_secret_value())
try:
    with engine.connect() as connection:
        roles = [
            dict(item._mapping)
            for item in connection.execute(
                text(
                    "SELECT rolname,rolsuper,rolbypassrls,rolcreaterole FROM pg_roles "
                    "WHERE rolname IN ('workbench_api','workbench_delivery','workbench_relay',"
                    "'workbench_scanner','workbench_worker') ORDER BY rolname"
                )
            )
        ]
        assert len(roles) == 5
        assert all(
            not row["rolsuper"] and not row["rolbypassrls"] and not row["rolcreaterole"]
            for row in roles
        )
        report["runtime_roles"] = roles
        protected = [
            dict(item._mapping)
            for item in connection.execute(
                text(
                    "SELECT relname,relrowsecurity,relforcerowsecurity FROM pg_class "
                    "WHERE relname IN ('applications','application_revisions','evidence_slots',"
                    "'upload_sessions','evidence_versions','evidence_derivatives','audit_events',"
                    "'access_events','operations_tasks') ORDER BY relname"
                )
            )
        ]
        assert len(protected) == 9 and all(
            row["relrowsecurity"] and row["relforcerowsecurity"] for row in protected
        )
        report["forced_rls"] = protected
        report["migration"] = connection.scalar(text("SELECT version_num FROM alembic_version"))
        report["synthetic_audit_chain"] = verify_stream(
            connection, "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa"
        )
        assert report["synthetic_audit_chain"]["valid"]
        report["query_plans"] = {
            "institution_cases": connection.scalar(
                text(
                    "EXPLAIN (FORMAT JSON) SELECT id FROM applications WHERE "
                    "institution_id='aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa' "
                    "ORDER BY created_at,id LIMIT 50"
                )
            ),
            "version_lookup": connection.scalar(
                text(
                    "EXPLAIN (FORMAT JSON) SELECT id FROM evidence_versions WHERE "
                    "clean_key='synthetic-query-plan' AND clean_version='synthetic-version'"
                )
            ),
        }
finally:
    engine.dispose()

docker = shutil.which("docker")
if docker is None:
    raise RuntimeError("Docker CLI is required for parser isolation verification")
inspection = (
    subprocess.check_output(  # noqa: S603 -- resolved binary, fixed inspect target/template.
        [
            docker,
            "inspect",
            "--format",
            "{{.HostConfig.NetworkMode}}|{{.Config.User}}|{{.HostConfig.ReadonlyRootfs}}|"
            "{{json .HostConfig.CapDrop}}|{{.HostConfig.Memory}}|{{.HostConfig.PidsLimit}}",
            "sih-foundation-parser-1",
        ],
        text=True,
        timeout=15,
    )
    .strip()
    .split("|")
)
assert inspection[0] == "none" and inspection[1] == "65532:65532" and inspection[2] == "true"
assert inspection[3] == '["ALL"]' and int(inspection[4]) == 1024**3
report["parser_isolation"] = dict(
    zip(
        ["network", "user", "read_only_root", "capabilities_dropped", "memory_bytes", "pids_limit"],
        inspection,
        strict=True,
    )
)
destination = PROJECT_ROOT / "artifacts/intake-platform.json"
destination.parent.mkdir(exist_ok=True)
destination.write_text(json.dumps(report, indent=2), encoding="utf-8")
print(json.dumps({"intake_platform": "PASS", "evidence": str(destination)}))
