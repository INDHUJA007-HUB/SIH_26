from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any
from uuid import uuid4

import jwt
import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from fastapi.testclient import TestClient

from workbench.api.app import create_app
from workbench.platform.config import PROJECT_ROOT, Settings


@pytest.fixture
def h(tmp_path, key_pair):
    import os

    from test_intake_integration import Harness

    if not os.environ.get("WB_INTEGRATION_DATABASE_URL"):
        pytest.skip("Phase 2–4 integration requires migrated local PostgreSQL")
    harness = Harness(tmp_path, key_pair)
    try:
        yield harness
    finally:
        harness.close()


def pytest_configure(config):
    if config.option.basetemp is None:
        temp_parent = PROJECT_ROOT / ".local" / "pytest"
        temp_parent.mkdir(parents=True, exist_ok=True)
        config.option.basetemp = str(temp_parent / uuid4().hex)


@pytest.fixture
def key_pair() -> tuple[bytes, bytes]:
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    return (
        key.private_bytes(
            serialization.Encoding.PEM,
            serialization.PrivateFormat.PKCS8,
            serialization.NoEncryption(),
        ),
        key.public_key().public_bytes(
            serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo
        ),
    )


@pytest.fixture
def settings(tmp_path: Path, key_pair: tuple[bytes, bytes]) -> Settings:
    public = tmp_path / "public.pem"
    public.write_bytes(key_pair[1])
    store = tmp_path / "fixtures.json"
    store.write_text(
        (PROJECT_ROOT / "backend/fixtures/foundation.json").read_text(), encoding="utf-8"
    )
    return Settings(
        _env_file=None,
        environment="test",
        fixture_public_key=public,
        fixture_store=store,
        database_url="",
        dependency_checks=False,
    )


@pytest.fixture
def client(settings: Settings):
    with TestClient(create_app(settings)) as test_client:
        yield test_client


@pytest.fixture
def issue_token(settings: Settings, key_pair: tuple[bytes, bytes]):
    def issue(**overrides: Any) -> str:
        now = datetime.now(UTC)
        claims = {
            "sub": "11111111-1111-4111-8111-111111111111",
            "iss": settings.auth_issuer,
            "aud": settings.auth_audience,
            "iat": now,
            "exp": now + timedelta(minutes=5),
        }
        claims.update(overrides)
        return jwt.encode(claims, key_pair[0], algorithm="RS256")

    return issue
