"""Verify local Keycloak token/issuer/audience and server mapping without disclosing credentials."""

import json
import time

import httpx
from fastapi.testclient import TestClient

from workbench.adapters.auth import JWTVerifier
from workbench.adapters.fixtures import FixtureDirectory
from workbench.api.app import create_app
from workbench.platform.config import Settings

settings = Settings(
    auth_mode="oidc",
    auth_issuer="http://127.0.0.1:8081/realms/sih-local",
    oidc_jwks_url="http://127.0.0.1:8081/realms/sih-local/protocol/openid-connect/certs",
    domain_enabled=True,
)
with httpx.Client(timeout=5) as client:
    for attempt in range(30):
        try:
            response = client.post(
                settings.auth_issuer + "/protocol/openid-connect/token",
                data={
                    "client_id": "workbench-api",
                    "grant_type": "password",
                    "username": "institution-a",
                    "password": "synthetic-local-login-only",
                },
            )
            response.raise_for_status()
            break
        except (httpx.HTTPError, KeyError):
            if attempt == 29:
                raise RuntimeError("Local identity provider did not become ready") from None
            time.sleep(2)
subject = JWTVerifier(settings).subject(response.json()["access_token"])
actor = FixtureDirectory(settings.fixture_store).lookup_actor(subject)
if actor is None or actor.institution_id != "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa":
    raise RuntimeError("OIDC subject did not match the server-side synthetic assignment")
with TestClient(create_app(settings)) as api:
    me = api.get(
        "/api/v1/me", headers={"Authorization": "Bearer " + response.json()["access_token"]}
    )
    assert me.status_code == 200 and me.json()["memberships"][0]["role"] == "institution_editor"
print(json.dumps({"oidc": "PASS", "synthetic_assignment": "PASS", "persisted_membership": "PASS"}))
