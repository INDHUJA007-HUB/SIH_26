"""Real S3/Temporal/ClamAV/networkless-parser acceptance, without mocked scan outcomes."""

import base64
import io
import os
import shutil
import subprocess
import time
from contextlib import suppress
from datetime import timedelta
from uuid import uuid4

import httpx
import pytest
from PIL import Image
from pypdf import PdfWriter
from sqlalchemy import func, select, update

from workbench.adapters import tables as t
from workbench.adapters.auth import JWTVerifier
from workbench.adapters.delivery_service import DeliveryService
from workbench.adapters.domain_store import now
from workbench.platform.config import PROJECT_ROOT

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(
        os.environ.get("WB_FILE_INTEGRATION") != "1", reason="Requires complete local scan stack"
    ),
]


def png():
    output = io.BytesIO()
    Image.new("RGB", (48, 32), (20, 70, 160)).save(output, format="PNG")
    return output.getvalue()


def pdf(encrypted=False, active=False, pages=1):
    writer = PdfWriter()
    for _ in range(pages):
        writer.add_blank_page(width=200, height=200)
    if encrypted:
        writer.encrypt("synthetic-password")
    if active:
        writer.add_js("app.alert('synthetic-test');")
    output = io.BytesIO()
    writer.write(output)
    return output.getvalue()


def put_grant(grant, data):
    response = httpx.put(grant["url"], headers=grant["headers"], content=data, timeout=15)
    assert response.is_success, (response.status_code, response.text[:200])
    return response.headers.get("x-amz-version-id")


def upload(harness, application, data, **options):
    session = harness.prepare_upload(application, data, **options)
    version = put_grant(session["grant"], data)
    response = harness.call(
        "POST", f"/api/v1/upload-sessions/{session['id']}/complete", json={"version_id": version}
    )
    assert response.status_code == 202, response.text
    return session, response.json()


def wait_result(harness, identifier):
    deadline = time.monotonic() + 90
    while time.monotonic() < deadline:
        response = harness.call("GET", "/api/v1/evidence/" + identifier)
        assert response.status_code == 200, response.text
        result = response.json()
        if result["status"] in {"ACCEPTED", "REJECTED"}:
            return result
        time.sleep(0.3)
    pytest.fail("Real scan did not reach a terminal result within 90 seconds")


def test_real_png_acceptance_ranges_previews_and_cross_owner_denial(h):
    data = png()
    application = h.create()
    _, evidence = upload(h, application, data)
    result = wait_result(h, evidence["id"])
    assert result["status"] == "ACCEPTED", result
    assert result["metadata"]["scanner"].startswith("ClamAV")
    assert "clean_key" not in result
    path = f"/api/v1/evidence/{evidence['id']}"
    response = h.call("GET", path + "/content")
    assert response.content == data
    assert "attachment" in response.headers["content-disposition"]
    assert response.headers["cache-control"] == "no-store"
    partial = h.call("GET", path + "/content", headers={"Range": "bytes=1-9"})
    assert partial.status_code == 206 and partial.content == data[1:10]
    assert partial.headers["content-range"] == f"bytes 1-9/{len(data)}"
    assert h.call("HEAD", path + "/content").content == b""
    assert h.call("GET", path + "/content", headers={"Range": "bytes=99999-"}).status_code == 416
    assert h.call("GET", path + "/content", headers={"Range": "bytes=0-2,5-6"}).status_code == 416
    assert h.call("GET", path + "/pages/1").content.startswith(b"\x89PNG")
    for suffix in ["", "/content", "/pages/1", "/access-events"]:
        assert h.call("GET", path + suffix, actor="b").status_code == 404
    assert (
        h.call("GET", path + "/content", actor="b", headers={"Range": "bytes=1-9"}).status_code
        == 404
    )
    events = h.call("GET", path + "/access-events").json()
    assert any(
        item["result"] == "COMPLETED" and item["bytes_served"] == len(data) for item in events
    )


@pytest.mark.parametrize(
    "data,media,reason",
    [
        (b"not a PNG", "image/png", "MIME_MISMATCH"),
        (b"%PDF-broken", "application/pdf", "MALFORMED_OR_RESOURCE_LIMIT"),
        (pdf(encrypted=True), "application/pdf", "ENCRYPTED_PDF_UNSUPPORTED"),
        (pdf(active=True), "application/pdf", "PDF_ACTIVE_CONTENT"),
        (pdf(pages=51), "application/pdf", "PAGE_LIMIT"),
        (
            b"X5O!P%@AP[4\\PZX54(P^)7CC)7}" + b"$EICAR-STANDARD-ANTIVIRUS-TEST-FILE!$H+H*",
            "image/png",
            "MALWARE_DETECTED",
        ),
    ],
)
def test_real_rejection_never_delivers_quarantine(h, data, media, reason):
    _, evidence = upload(h, h.create(), data, media_type=media)
    result = wait_result(h, evidence["id"])
    assert result["status"] == "REJECTED", result
    assert result["reason_code"] == reason, result
    assert h.call("GET", f"/api/v1/evidence/{evidence['id']}/content").status_code == 409
    with h.owner.connect() as connection:
        stored = connection.execute(
            select(t.evidence).where(t.evidence.c.id == evidence["id"])
        ).one()
        assert stored.clean_key is None


def test_pdf_renders_each_page_and_submission_freezes_exact_versions(h):
    application = h.create()
    data = pdf(pages=2)
    session, evidence = upload(h, application, data, media_type="application/pdf")
    result = wait_result(h, evidence["id"])
    assert result["status"] == "ACCEPTED", result
    assert result["metadata"]["page_count"] == 2
    assert h.call("GET", f"/api/v1/evidence/{evidence['id']}/pages/2").status_code == 200
    payload = {"expected_revision": 1, "evidence_ids": [evidence["id"]]}
    key = uuid4().hex
    response = h.call(
        "POST", f"/api/v1/applications/{application['id']}/submit", key=key, json=payload
    )
    assert response.status_code == 200, response.text
    history = h.call("GET", f"/api/v1/applications/{application['id']}/revisions").json()
    # Presigned PUT links can be reused until expiry; immutable captured versions must win.
    put_grant(session["grant"], data)
    assert h.call("GET", f"/api/v1/applications/{application['id']}/revisions").json() == history
    assert (
        h.call(
            "POST", f"/api/v1/applications/{application['id']}/submit", key=key, json=payload
        ).json()
        == response.json()
    )
    summary = h.call("GET", f"/api/v1/applications/{application['id']}/summary").json()
    assert summary["accepted_versions"] == 1 and summary["missing_slots"] == []


def test_pinned_quarantine_version_survives_a_new_latest_object(h):
    application, data = h.create(), png()
    session = h.prepare_upload(application, data)
    version = put_grant(session["grant"], data)
    with h.owner.connect() as connection:
        key = connection.scalar(
            select(t.uploads.c.object_key).where(t.uploads.c.id == session["id"])
        )
    h.storage.client.put_object(
        Bucket=h.storage.quarantine, Key=key, Body=b"hostile later object", ContentType="image/png"
    )
    response = h.call(
        "POST", f"/api/v1/upload-sessions/{session['id']}/complete", json={"version_id": version}
    )
    assert response.status_code == 202, response.text
    identifier = response.json()["id"]
    assert wait_result(h, identifier)["status"] == "ACCEPTED"
    assert h.call("GET", f"/api/v1/evidence/{identifier}/content").content == data


def test_incorrect_expected_checksum_is_rejected_by_real_worker(h):
    application, data = h.create(), png()
    session = h.prepare_upload(application, data, sha256="0" * 64)
    with h.owner.connect() as connection:
        key = connection.scalar(
            select(t.uploads.c.object_key).where(t.uploads.c.id == session["id"])
        )
    # Privileged fixture bypass emulates corrupted storage; no runtime client has this authority.
    version = h.storage.client.put_object(
        Bucket=h.storage.quarantine, Key=key, Body=data, ContentType="image/png"
    )["VersionId"]
    response = h.call(
        "POST", f"/api/v1/upload-sessions/{session['id']}/complete", json={"version_id": version}
    )
    assert response.status_code == 202, response.text
    assert wait_result(h, response.json()["id"])["reason_code"] == "CHECKSUM_MISMATCH"


def test_stream_close_before_first_byte_records_aborted_access(h):
    _, evidence = upload(h, h.create(), png())
    assert wait_result(h, evidence["id"])["status"] == "ACCEPTED"
    service = DeliveryService(h.app.state.domain_store, h.storage)
    principal = JWTVerifier(h.settings).principal(h.token())
    stream, _, _ = service.prepare(principal, evidence["id"], None, None, uuid4().hex)
    stream.close()
    events = h.call("GET", f"/api/v1/evidence/{evidence['id']}/access-events").json()
    assert any(item["result"] == "ABORTED" and item["bytes_served"] == 0 for item in events)


def test_multipart_completion_checks_missing_parts_and_whole_file(h):
    data = png()
    session = h.prepare_upload(h.create(), data, mode="MULTIPART")
    path = f"/api/v1/upload-sessions/{session['id']}"
    assert h.call("POST", path + "/complete", json={}).status_code == 409
    assert h.call("GET", path + "/parts/2").status_code == 422
    grant = h.call("GET", path + "/parts/1").json()
    put_grant(grant, data)
    response = h.call("POST", path + "/complete", json={})
    assert response.status_code == 202, response.text
    assert wait_result(h, response.json()["id"])["status"] == "ACCEPTED"
    assert h.call("GET", f"/api/v1/evidence/{response.json()['id']}/content").content == data


def test_two_part_upload_rejects_wrong_part_size_then_accepts_valid_bytes(h):
    output = io.BytesIO()
    Image.frombytes("RGB", (1800, 1100), os.urandom(1800 * 1100 * 3)).save(output, format="PNG")
    data = output.getvalue()
    session = h.prepare_upload(h.create(), data, mode="MULTIPART")
    assert session["part_count"] == 2
    path = f"/api/v1/upload-sessions/{session['id']}"
    grants = [h.call("GET", path + f"/parts/{number}").json() for number in (1, 2)]
    put_grant(grants[0], b"wrong planned length")
    put_grant(grants[1], data[session["part_size"] :])
    assert h.call("POST", path + "/complete", json={}).status_code == 409
    put_grant(grants[0], data[: session["part_size"]])
    response = h.call("POST", path + "/complete", json={})
    assert response.status_code == 202, response.text
    assert wait_result(h, response.json()["id"])["status"] == "ACCEPTED"


def test_retained_original_survives_reconciliation_and_missing_derivative_is_reported(h):
    from workbench.adapters.reconciliation import reconcile_once
    from workbench.platform.config import Settings

    application = h.create()
    _, evidence = upload(h, application, png())
    assert wait_result(h, evidence["id"])["status"] == "ACCEPTED"
    with h.owner.begin() as connection:
        derivative = connection.execute(
            select(t.derivatives).where(t.derivatives.c.evidence_id == evidence["id"])
        ).one()
        # Restart bounded cursors for this fault probe so the freshly-created fixture is examined.
        connection.execute(t.reconciliation_cursors.delete())
    h.storage.client.delete_object(
        Bucket=h.storage.clean, Key=derivative.object_key, VersionId=derivative.object_version
    )
    reconcile_once(Settings())
    tasks = h.call("GET", f"/api/v1/applications/{application['id']}/tasks").json()
    assert any(item["kind"] == "MISSING_DERIVATIVE_OBJECT" for item in tasks)
    assert h.call("GET", f"/api/v1/evidence/{evidence['id']}/content").content == png()


def test_real_video_inspection_is_metadata_only_and_preserves_original(h):
    data = base64.b64decode((PROJECT_ROOT / "backend/fixtures/synthetic-video.base64").read_text())
    _, evidence = upload(h, h.create(), data, media_type="video/mp4", filename="fixture.mp4")
    result = wait_result(h, evidence["id"])
    assert result["status"] == "ACCEPTED", result
    assert result["metadata"]["duration_seconds"] == 1
    assert result["metadata"]["streams"][0]["width"] == 32
    assert h.call("GET", f"/api/v1/evidence/{evidence['id']}/content").content == data


@pytest.mark.skipif(
    os.environ.get("WB_CHAOS_INTEGRATION") != "1", reason="Opt-in local service outage probe"
)
def test_parser_outage_times_out_closed_then_recovers(h):
    docker = shutil.which("docker")
    assert docker
    prefix = [docker, "compose", "--env-file", ".env", "-f", "infra/compose/compose.yaml"]

    def compose(action):
        cmd = (
            [*prefix, "up", "-d", "--no-deps", "parser"]
            if action == "start"
            else [*prefix, "stop", "parser"]
        )
        subprocess.run(  # noqa: S603 -- resolved CLI, fixed compose file/service, internal actions.
            cmd,
            cwd=PROJECT_ROOT,
            check=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            timeout=30,
        )

    compose("stop")
    try:
        application = h.create()
        _, evidence = upload(h, application, png())
        deadline = time.monotonic() + 75
        while time.monotonic() < deadline:
            result = h.call("GET", f"/api/v1/evidence/{evidence['id']}").json()
            if result["status"] == "SCAN_FAILED":
                break
            time.sleep(0.3)
        assert result["status"] == "SCAN_FAILED", result
        assert h.call("GET", f"/api/v1/evidence/{evidence['id']}/content").status_code == 409
        tasks = h.call("GET", f"/api/v1/applications/{application['id']}/tasks").json()
        assert any(task["kind"] == "SCAN_RETRY_REQUIRED" for task in tasks)
    finally:
        with suppress(Exception):
            compose("start")
    assert wait_result(h, evidence["id"])["status"] == "ACCEPTED"


@pytest.mark.skipif(
    os.environ.get("WB_CHAOS_INTEGRATION") != "1", reason="Opt-in local relay outage probe"
)
def test_committed_outbox_survives_unavailable_temporal_and_repeated_delivery(h):
    import asyncio

    from workbench.platform.config import Settings
    from workbench.platform.outbox import dispatch_once

    docker = shutil.which("docker")
    assert docker
    prefix = [docker, "compose", "--env-file", ".env", "-f", "infra/compose/compose.yaml"]

    def compose(action):
        cmd = (
            [*prefix, "up", "-d", "--no-deps", "outbox-relay"]
            if action == "start"
            else [*prefix, "stop", "outbox-relay"]
        )
        subprocess.run(  # noqa: S603 -- fixed local service and internal action values.
            cmd,
            cwd=PROJECT_ROOT,
            check=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            timeout=30,
        )

    compose("stop")
    try:
        application = h.create()
        response = h.call(
            "POST",
            f"/api/v1/applications/{application['id']}/submit",
            json={"expected_revision": 1, "evidence_ids": []},
        )
        assert response.status_code == 200
        event = response.json()["event_id"]
        with pytest.raises((RuntimeError, TimeoutError, ConnectionError, OSError)):
            asyncio.run(dispatch_once(Settings(temporal_address="127.0.0.1:1")))
        with h.owner.begin() as connection:
            stored = connection.execute(select(t.outbox).where(t.outbox.c.id == event)).one()
            assert stored.delivered_at is None
            connection.execute(
                update(t.outbox)
                .where(t.outbox.c.id == event)
                .values(
                    lease_until=now() - timedelta(seconds=1),
                    available_at=now(),
                )
            )
        compose("start")

        def wait_receipt():
            deadline = time.monotonic() + 30
            while time.monotonic() < deadline:
                with h.owner.connect() as connection:
                    if connection.scalar(
                        select(t.receipts.c.event_id).where(t.receipts.c.event_id == event)
                    ):
                        return
                time.sleep(0.2)
            pytest.fail("Committed event was not acknowledged after the relay recovered")

        wait_receipt()
        with h.owner.begin() as connection:
            connection.execute(
                update(t.outbox)
                .where(t.outbox.c.id == event)
                .values(
                    delivered_at=None,
                    lease_until=None,
                    available_at=now(),
                )
            )
        deadline = time.monotonic() + 15
        while time.monotonic() < deadline:
            with h.owner.connect() as connection:
                if connection.scalar(select(t.outbox.c.delivered_at).where(t.outbox.c.id == event)):
                    assert (
                        connection.scalar(
                            select(func.count())
                            .select_from(t.receipts)
                            .where(t.receipts.c.event_id == event)
                        )
                        == 1
                    )
                    assert (
                        connection.scalar(
                            select(func.count())
                            .select_from(t.tasks)
                            .where(t.tasks.c.resource_id == event)
                        )
                        == 1
                    )
                    break
            time.sleep(0.2)
        else:
            pytest.fail("Repeated workflow start was not acknowledged")
    finally:
        with suppress(Exception):
            compose("start")
