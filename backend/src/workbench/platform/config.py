"""Validated configuration. Secrets never enter public build/health responses."""

import os
from functools import lru_cache
from pathlib import Path
from typing import Literal, Self

from pydantic import Field, SecretStr, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

PROJECT_ROOT = Path(
    os.environ.get("WB_PROJECT_ROOT", Path(__file__).resolve().parents[4])
).resolve()


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="WB_", env_file=PROJECT_ROOT / ".env", extra="ignore"
    )

    environment: Literal["local", "test", "integration", "staging", "production"] = "local"
    service_name: str = "workbench-api"
    build_revision: str = Field(default="working-tree", max_length=80)
    auth_mode: Literal["fixture", "oidc"] = "fixture"
    fixture_store: Path = PROJECT_ROOT / ".local" / "fixtures.json"
    fixture_public_key: Path = PROJECT_ROOT / ".local" / "fixture-public.pem"
    auth_issuer: str = "urn:sih:local-fixture"
    auth_audience: str = "workbench-api"
    oidc_jwks_url: str = ""
    database_url: SecretStr = SecretStr("")
    dependency_checks: bool = False
    temporal_address: str = "127.0.0.1:7233"
    temporal_namespace: str = "default"
    temporal_task_queue: str = "foundation"
    s3_endpoint: str = "http://127.0.0.1:5000"
    s3_access_key: SecretStr = SecretStr("local-simulator")
    s3_secret_key: SecretStr = SecretStr("local-simulator")
    s3_region: str = "ap-south-1"
    s3_buckets: tuple[str, ...] = ("sih-quarantine", "sih-evidence", "sih-reports")
    telemetry_enabled: bool = False
    otlp_endpoint: str = "http://127.0.0.1:4318/v1/traces"
    expose_local_metrics: bool = True
    domain_enabled: bool = False
    app_database_url: SecretStr = SecretStr("")
    delivery_database_url: SecretStr = SecretStr("")
    relay_database_url: SecretStr = SecretStr("")
    scan_database_url: SecretStr = SecretStr("")
    worker_database_url: SecretStr = SecretStr("")
    s3_public_endpoint: str = "http://127.0.0.1:5000"
    max_upload_bytes: int = Field(default=25 * 1024 * 1024, ge=1, le=100 * 1024 * 1024)
    institution_quota_bytes: int = Field(default=500 * 1024 * 1024, ge=1)
    actor_quota_bytes: int = Field(default=250 * 1024 * 1024, ge=1)
    max_pending_uploads: int = Field(default=10, ge=1, le=100)
    upload_ttl_seconds: int = Field(default=900, ge=60, le=3600)
    multipart_part_bytes: int = Field(default=5 * 1024 * 1024, ge=5 * 1024 * 1024)
    step_up_seconds: Literal[300] = 300  # Versioned database policy fixes the same window.
    scanner_host: str = "127.0.0.1"
    scanner_port: int = 3310
    scanner_max_signature_age_hours: int = 72
    scan_input_directory: Path = PROJECT_ROOT / ".local/scan-input"
    scan_output_directory: Path = PROJECT_ROOT / ".local/scan-output"
    parser_timeout_seconds: int = Field(default=45, ge=5, le=120)
    max_pdf_pages: int = Field(default=50, ge=1, le=100)
    max_video_seconds: int = Field(default=3600, ge=1, le=7200)

    @model_validator(mode="after")
    def validate_modes(self) -> Self:
        if self.environment not in {"local", "test"} and self.auth_mode == "fixture":
            raise ValueError("Fixture authentication is allowed only in local/test environments")
        if self.environment in {"staging", "production"}:
            raise ValueError("This development release is not qualified for staging/production")
        if self.auth_mode == "oidc" and not self.oidc_jwks_url:
            raise ValueError("OIDC mode requires WB_OIDC_JWKS_URL")
        if self.dependency_checks and not self.database_url.get_secret_value():
            raise ValueError("Dependency checks require WB_DATABASE_URL")
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()
