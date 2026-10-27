"""Create a real API-backed synthetic Phase 4 demonstration packet on the local stack."""

import hashlib
import io
import json
import time
from uuid import uuid4

import httpx
from PIL import Image, ImageDraw

from workbench.platform.config import PROJECT_ROOT, Settings
from workbench.tools import fixture_token

settings = Settings()
if settings.environment != "local" or settings.auth_mode != "fixture":
    raise SystemExit("This seed is restricted to the local synthetic fixture profile")
image = Image.new("RGB", (800, 400), "white")
draw = ImageDraw.Draw(image)
draw.text((50, 80), "SYNTHETIC EVIDENCE - DEVELOPMENT ONLY", fill="black")
draw.text((50, 150), "Not an AICTE approval, certificate or issuer verification.", fill="black")
output = io.BytesIO()
image.save(output, format="PNG")
data = output.getvalue()
with httpx.Client(
    base_url="http://127.0.0.1:8000",
    timeout=15,
    headers={"Authorization": "Bearer " + fixture_token(settings)},
) as api:

    def command(path, body):
        result = api.post("/api/v1/" + path, json=body, headers={"Idempotency-Key": uuid4().hex})
        result.raise_for_status()
        return result.json()

    application = command(
        "applications",
        {
            "institution_id": "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa",
            "category": "SYNTHETIC_DEMO",
            "cycle_start": 2026,
            "programme": "ENGINEERING_AND_TECHNOLOGY",
            "level": "UG",
            "declared_facts": {"demo": {"value": True, "basis": "SYNTHETIC DEVELOPMENT FIXTURE"}},
            "slots": [{"code": "SYNTHETIC_DOCUMENT", "required": True}],
        },
    )
    application_path = "applications/" + application["id"]
    detail = api.get("/api/v1/" + application_path).json()
    upload = command(
        application_path + "/upload-sessions",
        {
            "slot_id": detail["slots"][0]["id"],
            "filename": "SYNTHETIC-DEMO.png",
            "media_type": "image/png",
            "size_bytes": len(data),
            "sha256": hashlib.sha256(data).hexdigest(),
            "mode": "SINGLE",
        },
    )
    grant = upload["grant"]
    response = httpx.put(grant["url"], headers=grant["headers"], content=data, timeout=15)
    response.raise_for_status()
    evidence = command(
        "upload-sessions/" + upload["id"] + "/complete",
        {"version_id": response.headers["x-amz-version-id"]},
    )
    deadline = time.monotonic() + 90
    while time.monotonic() < deadline:
        state = api.get("/api/v1/evidence/" + evidence["id"]).json()
        if state["status"] in {"ACCEPTED", "REJECTED"}:
            break
        time.sleep(0.3)
    if state["status"] != "ACCEPTED":
        raise SystemExit("Synthetic demo evidence did not pass the complete inspection pipeline")
    submission = command(
        application_path + "/submit",
        {
            "expected_revision": 1,
            "evidence_ids": [evidence["id"]],
        },
    )
    summary = api.get("/api/v1/" + application_path + "/summary").json()
    report = {
        "synthetic": True,
        "application": submission,
        "evidence_id": evidence["id"],
        "summary": summary,
        "api_path": "/api/v1/" + application_path,
    }
    (PROJECT_ROOT / "artifacts/intake-demo.json").write_text(json.dumps(report, indent=2))
    print(json.dumps(report, indent=2))
