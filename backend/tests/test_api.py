from datetime import UTC, datetime, timedelta

import jwt
import pytest


def test_health_build_and_openapi_do_not_disclose_configuration(client):
    for path in ("/health/live", "/health/ready", "/version", "/openapi.json"):
        response = client.get(path)
        assert response.status_code == 200
        assert "database_url" not in response.text
        assert "secret_key" not in response.text
        assert response.headers["cache-control"] == "no-store"


def test_fixture_requires_authentication(client):
    response = client.get("/api/v1/foundation/fixture")
    assert response.status_code == 401
    assert response.headers["www-authenticate"] == "Bearer"
    assert response.json()["request_id"] == response.headers["x-request-id"]


def test_fixture_uses_server_assignment_not_client_roles(client, issue_token):
    token = issue_token(roles=["admin"], institution_id="bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb")
    response = client.get(
        "/api/v1/foundation/fixture?institution_id=other",
        headers={
            "Authorization": f"Bearer {token}",
        },
    )
    assert response.status_code == 200
    assert response.json()["institution"]["id"] == "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa"


def test_second_identity_gets_only_its_fixture(client, issue_token):
    token = issue_token(sub="22222222-2222-4222-8222-222222222222")
    response = client.get(
        "/api/v1/foundation/fixture", headers={"Authorization": f"Bearer {token}"}
    )
    assert response.json()["institution"]["id"] == "bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb"


@pytest.mark.parametrize(
    "claims",
    [
        {"iss": "untrusted"},
        {"aud": "wrong-service"},
        {"exp": datetime.now(UTC) - timedelta(minutes=1)},
    ],
)
def test_invalid_claims_denied(client, issue_token, claims):
    response = client.get(
        "/api/v1/foundation/fixture",
        headers={
            "Authorization": f"Bearer {issue_token(**claims)}",
        },
    )
    assert response.status_code == 401


def test_unknown_subject_cannot_claim_an_admin_role(client, issue_token):
    response = client.get(
        "/api/v1/foundation/fixture",
        headers={
            "Authorization": f"Bearer {issue_token(sub='unassigned', roles=['admin'])}",
        },
    )
    assert response.status_code == 403


def test_unsigned_token_is_rejected(client):
    token = jwt.encode({"sub": "11111111-1111-4111-8111-111111111111"}, "", algorithm="none")
    assert (
        client.get(
            "/api/v1/foundation/fixture",
            headers={
                "Authorization": f"Bearer {token}",
            },
        ).status_code
        == 401
    )


def test_request_id_is_bounded_and_safe(client):
    response = client.get("/version", headers={"x-request-id": "malformed/<identifier>"})
    assert response.headers["x-request-id"] != "malformed/<identifier>"
    assert len(response.headers["x-request-id"]) == 36


def test_capabilities_are_honest_and_metrics_use_routes(client):
    assert client.get("/api/v1/capabilities").json()["live_source_verification"] is False
    client.get("/unknown-sensitive-identifier")
    metrics = client.get("/metrics").text
    assert 'route="unmatched"' in metrics
    assert "unknown-sensitive-identifier" not in metrics
