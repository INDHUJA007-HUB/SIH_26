"""Create synthetic demo records through the real local authenticated APIs."""

import argparse
import json
from datetime import UTC, datetime, timedelta
from pathlib import Path
from urllib.parse import urlparse
from uuid import uuid4

import httpx

from workbench.platform.config import Settings
from workbench.tools import fixture_token


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", default="http://127.0.0.1:8000")
    args = parser.parse_args()
    parsed = urlparse(args.base_url)
    settings = Settings()
    if parsed.hostname not in {"127.0.0.1", "localhost"} or parsed.scheme != "http":
        raise ValueError("The synthetic demo seed is restricted to loopback HTTP")
    if settings.environment not in {"local", "test"} or settings.auth_mode != "fixture":
        raise ValueError("Use the local synthetic fixture profile, never an OIDC deployment")
    subjects = {
        "institution": "11111111-1111-4111-8111-111111111111",
        "supervisor": "55555555-5555-4555-8555-555555555555",
        "author": "77777777-7777-4777-8777-777777777777",
        "approver": "88888888-8888-4888-8888-888888888888",
    }
    tokens = {
        role: fixture_token(settings, subject, mfa=role != "institution")
        for role, subject in subjects.items()
    }
    with httpx.Client(base_url=args.base_url, timeout=60) as client:

        def post(path: str, role: str, data: dict) -> dict:
            response = client.post(
                "/api/v1" + path,
                json=data,
                headers={"Authorization": "Bearer " + tokens[role], "Idempotency-Key": uuid4().hex},
            )
            if not response.is_success:
                raise RuntimeError(f"{path}: {response.status_code} {response.text}")
            return response.json()

        pack_data = json.loads(
            (Path(__file__).parents[1] / "fixtures/niyam_demo_pack.json").read_text()
        )
        pack = post("/process-packs", "author", pack_data)
        post(
            f"/process-packs/{pack['id']}/publish",
            "approver",
            {"source_review": "Synthetic demonstration only; not an official policy publication"},
        )
        app = post(
            "/applications",
            "institution",
            {
                "institution_id": "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa",
                "category": "NEW_INSTITUTE",
                "cycle_start": pack_data["academic_cycle"],
                "programme": "ENGINEERING_AND_TECHNOLOGY",
                "level": "UG",
                "declared_facts": {"synthetic_niyam_demo": True},
                "slots": [{"code": "RENEWAL", "required": False}],
            },
        )
        post(
            f"/applications/{app['id']}/submit",
            "institution",
            {"expected_revision": app["revision"]},
        )
        case = post(
            "/approval-cases", "supervisor", {"application_id": app["id"], "pack_id": pack["id"]}
        )
        watch = post(
            "/obligations",
            "supervisor",
            {
                "institution_id": case["institution_id"],
                "application_id": app["id"],
                "case_id": case["id"],
                "pack_id": pack["id"],
                "kind": "DOCUMENT_VALIDITY",
                "code": "DEMO_LEASE",
                "title": "Demonstration lease renewal",
                "source_reference": "SYNTHETIC lease record, page 1",
                "due_at": (datetime.now(UTC) - timedelta(days=1)).isoformat(),
            },
        )
        start = datetime.now(UTC) + timedelta(days=2)
        roster = post(
            "/evc-rosters",
            "supervisor",
            {
                "region": case["region"],
                "source_reference": "SYNTHETIC authorized online committee order",
                "members": ["SYNTHETIC_EXPERT_A", "SYNTHETIC_EXPERT_B"],
                "mode": "ONLINE",
                "availability": [
                    {
                        "starts_at": start.isoformat(),
                        "ends_at": (start + timedelta(hours=1)).isoformat(),
                    }
                ],
                "expires_at": (start + timedelta(days=1)).isoformat(),
            },
        )
    print(
        json.dumps(
            {
                "synthetic": True,
                "workspace": args.base_url + "/niyam",
                "case_id": case["id"],
                "application_id": app["id"],
                "pack_id": pack["id"],
                "document_watch_id": watch["id"],
                "roster_id": roster["id"],
                "next_step": "Use a local fixture token in the workspace",
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
