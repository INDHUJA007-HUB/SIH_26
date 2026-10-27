"""Verify actual local platform behavior and write a content-free verification artifact."""

import asyncio
import hashlib
import json
import time
from uuid import uuid4

import boto3
import httpx
from dotenv import dotenv_values

from workbench.platform.config import PROJECT_ROOT, Settings
from workbench.tools import api_smoke, seed_buckets, seed_database, workflow_smoke


def main() -> None:
    settings = Settings()
    report = {
        "scope": "LOCAL_SYNTHETIC_PHASE_1",
        "api": api_smoke(settings, "http://127.0.0.1:8000"),
    }
    report["database_seed"] = seed_database(settings)
    assert seed_database(settings) == report["database_seed"]
    report["storage"] = seed_buckets(settings)
    client = boto3.client(
        "s3",
        endpoint_url=settings.s3_endpoint,
        region_name=settings.s3_region,
        aws_access_key_id=settings.s3_access_key.get_secret_value(),
        aws_secret_access_key=settings.s3_secret_key.get_secret_value(),
    )
    bucket, key = settings.s3_buckets[0], f"foundation-spike/{uuid4().hex}"
    first = client.put_object(Bucket=bucket, Key=key, Body=b"synthetic-version-one")
    url = client.generate_presigned_url(
        "put_object", Params={"Bucket": bucket, "Key": key}, ExpiresIn=60
    )
    with httpx.Client(timeout=10) as http:
        http.put(url, content=b"synthetic-version-two").raise_for_status()
        http.put(url, content=b"synthetic-version-three").raise_for_status()
        original = client.get_object(Bucket=bucket, Key=key, VersionId=first["VersionId"])[
            "Body"
        ].read()
        assert (
            hashlib.sha256(original).digest() == hashlib.sha256(b"synthetic-version-one").digest()
        )
        assert (
            client.get_object(Bucket=bucket, Key=key)["Body"].read() == b"synthetic-version-three"
        )
        report["version_and_reused_grant_probe"] = "PASS_LOCAL_SIMULATOR_ONLY"
        for name, endpoint in {
            "mailpit": "http://127.0.0.1:8025/api/v1/messages",
            "grafana": "http://127.0.0.1:3000/api/health",
        }.items():
            http.get(endpoint).raise_for_status()
            report[name] = "PASS"
        values = dotenv_values(PROJECT_ROOT / ".env")
        dashboard = http.get(
            "http://127.0.0.1:3000/api/dashboards/uid/workbench-foundation",
            auth=("local-admin", str(values["GRAFANA_ADMIN_PASSWORD"])),
        )
        dashboard.raise_for_status()
        assert dashboard.json()["dashboard"]["uid"] == "workbench-foundation"
        report["provisioned_dashboard"] = "PASS"
        for attempt in range(20):
            query = http.get(
                "http://127.0.0.1:9090/api/v1/query", params={"query": 'up{job="workbench-api"}'}
            ).json()
            services = http.get("http://127.0.0.1:16686/api/v3/services").json()
            if (
                query["data"]["result"]
                and query["data"]["result"][0]["value"][1] == "1"
                and ("workbench-api" in services.get("services", []))
            ):
                break
            if attempt == 19:
                raise RuntimeError(
                    "Metrics or request traces did not reach the local dashboard stack"
                )
            time.sleep(2)
        report["prometheus_scrape"] = "PASS"
        report["collector_to_jaeger"] = "PASS"
    report["workflow"] = asyncio.run(workflow_smoke(settings))
    destination = PROJECT_ROOT / "artifacts/platform-smoke.json"
    destination.parent.mkdir(exist_ok=True)
    destination.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
