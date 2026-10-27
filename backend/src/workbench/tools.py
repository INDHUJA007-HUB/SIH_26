"""Explicit local bootstrap, synthetic seeding, token, and platform smoke commands."""

import argparse
import asyncio
import json
import secrets
import shutil
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import boto3
import httpx
import jwt
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from sqlalchemy.orm import Session
from temporalio.client import Client

from workbench.platform.config import PROJECT_ROOT, Settings
from workbench.platform.database import FoundationInstitution, SeedRuleCandidate, build_engine

DEFAULT_SUBJECT = "11111111-1111-4111-8111-111111111111"


def bootstrap(root: Path = PROJECT_ROOT) -> dict[str, Any]:
    state = root / ".local"
    state.mkdir(exist_ok=True)
    private_path = state / "fixture-private.pem"
    public_path = state / "fixture-public.pem"
    if not private_path.exists():
        key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        private_path.write_bytes(
            key.private_bytes(
                serialization.Encoding.PEM,
                serialization.PrivateFormat.PKCS8,
                serialization.NoEncryption(),
            )
        )
        public_path.write_bytes(
            key.public_key().public_bytes(
                serialization.Encoding.PEM,
                serialization.PublicFormat.SubjectPublicKeyInfo,
            )
        )
    elif not public_path.exists():
        raise RuntimeError("Local key pair is incomplete; preserve state and repair it explicitly")
    target = state / "fixtures.json"
    if not target.exists():
        shutil.copyfile(root / "backend/fixtures/foundation.json", target)
    env = root / ".env"
    if not env.exists():
        password = secrets.token_urlsafe(24)
        env.write_text(
            "WB_ENVIRONMENT=local\nWB_AUTH_MODE=fixture\n"
            "WB_AUTH_ISSUER=urn:sih:local-fixture\nWB_AUTH_AUDIENCE=workbench-api\n"
            "WB_DEPENDENCY_CHECKS=false\nWB_TELEMETRY_ENABLED=false\n"
            f"POSTGRES_PASSWORD={password}\n"
            f"WB_DATABASE_URL=postgresql+psycopg://workbench:{password}@127.0.0.1:5432/workbench\n"
            f"KEYCLOAK_ADMIN_PASSWORD={secrets.token_urlsafe(24)}\n"
            f"GRAFANA_ADMIN_PASSWORD={secrets.token_urlsafe(24)}\n",
            encoding="utf-8",
        )
    rules = json.loads(
        (root / "output/AICTE_PS26261_Rule_Evidence_Register.json").read_text(encoding="utf-8")
    )
    for rule in rules["rules"]:
        if rule["production_enabled"] or rule["adverse_action_allowed"]:
            raise ValueError("Research rules must remain disabled")
    (state / "rule-candidates.json").write_text(json.dumps(rules, indent=2), encoding="utf-8")
    from workbench.platform.domain_bootstrap import ensure_local_credentials

    ensure_local_credentials(root)
    return {
        "synthetic": True,
        "institutions": 2,
        "draft_rules": len(rules["rules"]),
        "production_rules": 0,
        "state_directory": str(state),
    }


def fixture_token(settings: Settings, subject: str = DEFAULT_SUBJECT, mfa: bool = False) -> str:
    if settings.environment not in {"local", "test"} or settings.auth_mode != "fixture":
        raise ValueError("Token generation is restricted to local/test fixture mode")
    now = datetime.now(UTC)
    return jwt.encode(
        {
            "sub": subject,
            "iss": settings.auth_issuer,
            "aud": settings.auth_audience,
            "iat": now,
            "exp": now + timedelta(minutes=10),
            "jti": secrets.token_hex(16),
            "auth_time": int(now.timestamp()),
            "amr": ["pwd", "mfa"] if mfa else ["pwd"],
        },
        (PROJECT_ROOT / ".local/fixture-private.pem").read_bytes(),
        algorithm="RS256",
    )


def seed_database(settings: Settings) -> dict[str, Any]:
    if settings.environment not in {"local", "test", "integration"}:
        raise ValueError("Synthetic seeding is restricted to development environments")
    fixtures = json.loads(settings.fixture_store.read_text(encoding="utf-8"))
    rules = json.loads((PROJECT_ROOT / ".local/rule-candidates.json").read_text(encoding="utf-8"))
    engine = build_engine(settings.database_url.get_secret_value())
    try:
        with Session(engine) as session, session.begin():
            for institution in fixtures["institutions"]:
                session.merge(FoundationInstitution(**institution))
            for rule in rules["rules"]:
                if rule["production_enabled"] or rule["adverse_action_allowed"]:
                    raise ValueError("Cannot import enabled research rules")
                session.merge(
                    SeedRuleCandidate(
                        rule_id=rule["rule_id"],
                        publication_state="DRAFT",
                        production_enabled=False,
                        adverse_action_allowed=False,
                        source_sha256=rule["source_sha256"],
                        payload=rule,
                    )
                )
    finally:
        engine.dispose()
    return {"institutions": len(fixtures["institutions"]), "draft_rules": len(rules["rules"])}


def seed_buckets(settings: Settings) -> dict[str, Any]:
    client = boto3.client(
        "s3",
        endpoint_url=settings.s3_endpoint,
        region_name=settings.s3_region,
        aws_access_key_id=settings.s3_access_key.get_secret_value(),
        aws_secret_access_key=settings.s3_secret_key.get_secret_value(),
    )
    existing = {item["Name"] for item in client.list_buckets()["Buckets"]}
    for name in settings.s3_buckets:
        if name not in existing:
            client.create_bucket(
                Bucket=name,
                CreateBucketConfiguration={
                    "LocationConstraint": settings.s3_region,
                },
            )
        client.put_bucket_versioning(Bucket=name, VersioningConfiguration={"Status": "Enabled"})
        client.put_public_access_block(
            Bucket=name,
            PublicAccessBlockConfiguration={
                "BlockPublicAcls": True,
                "IgnorePublicAcls": True,
                "BlockPublicPolicy": True,
                "RestrictPublicBuckets": True,
            },
        )
        client.put_bucket_encryption(
            Bucket=name,
            ServerSideEncryptionConfiguration={
                "Rules": [{"ApplyServerSideEncryptionByDefault": {"SSEAlgorithm": "AES256"}}],
            },
        )
        if name == settings.s3_buckets[0]:
            client.put_bucket_lifecycle_configuration(
                Bucket=name,
                LifecycleConfiguration={
                    "Rules": [
                        {
                            "ID": "abort-incomplete-multipart",
                            "Status": "Enabled",
                            "Filter": {"Prefix": "quarantine/"},
                            "AbortIncompleteMultipartUpload": {"DaysAfterInitiation": 1},
                        }
                    ],
                },
            )
    return {"buckets": list(settings.s3_buckets), "provider": "LOCAL_S3_SIMULATOR"}


async def workflow_smoke(settings: Settings) -> dict[str, Any]:
    from workbench.workflows.foundation import FoundationWorkflow

    client = await Client.connect(settings.temporal_address, namespace=settings.temporal_namespace)
    workflow_id = f"foundation-smoke-{secrets.token_hex(8)}"
    result = await client.execute_workflow(
        FoundationWorkflow.run,
        "synthetic-fixture",
        id=workflow_id,
        task_queue=settings.temporal_task_queue,
        execution_timeout=timedelta(seconds=45),
    )
    return {"workflow_id": workflow_id, "result": result}


def api_smoke(settings: Settings, base_url: str) -> dict[str, Any]:
    with httpx.Client(base_url=base_url, timeout=10) as client:
        health = client.get("/health/live")
        health.raise_for_status()
        denied = client.get("/api/v1/foundation/fixture")
        if denied.status_code != 401:
            raise RuntimeError("Unauthenticated fixture request was not rejected")
        response = client.get(
            "/api/v1/foundation/fixture",
            headers={
                "Authorization": f"Bearer {fixture_token(settings)}",
            },
        )
        response.raise_for_status()
        payload = response.json()
        if not payload["institution"]["synthetic"]:
            raise RuntimeError("Smoke response is not synthetic")
        return {
            "health": health.status_code,
            "unauthenticated": denied.status_code,
            "authenticated": response.status_code,
            "response": payload,
        }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "command",
        choices=[
            "bootstrap",
            "token",
            "seed-db",
            "seed-buckets",
            "workflow-smoke",
            "api-smoke",
            "doctor",
            "seed-domain",
        ],
    )
    parser.add_argument("--subject", default=DEFAULT_SUBJECT)
    parser.add_argument("--mfa", action="store_true", help="Simulated local signed assurance only")
    parser.add_argument("--base-url", default="http://127.0.0.1:8000")
    args = parser.parse_args()
    if args.command == "bootstrap":
        result = bootstrap()
    elif args.command == "doctor":
        result = {
            "docker_cli": shutil.which("docker") is not None,
            "python_profile": "3.12",
            "state_exists": (PROJECT_ROOT / ".local").exists(),
        }
    else:
        settings = Settings()
        if args.command == "token":
            print(fixture_token(settings, args.subject, args.mfa))
            return
        if args.command == "seed-domain":
            from workbench.platform.domain_bootstrap import seed_domain

            result = seed_domain(settings)
        elif args.command == "seed-db":
            result = seed_database(settings)
        elif args.command == "seed-buckets":
            result = seed_buckets(settings)
        elif args.command == "workflow-smoke":
            result = asyncio.run(workflow_smoke(settings))
        else:
            result = api_smoke(settings, args.base_url)
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
