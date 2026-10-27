# Configuration reference

Configuration is typed by `workbench.platform.config.Settings`, uses the `WB_` prefix and optional repository `.env`, and validates unsafe mode combinations. Secret fields use secret types and are excluded from responses/logs.

| Variable | Default / required behavior |
| --- | --- |
| WB_ENVIRONMENT | `local`; `test` and `integration` supported; staging/production rejected for this foundation |
| WB_AUTH_MODE | `fixture` only in local/test; `oidc` requires issuer/audience/JWKS |
| WB_AUTH_ISSUER | `urn:sih:local-fixture`; exact expected issuer, never caller selected |
| WB_AUTH_AUDIENCE | `workbench-api` |
| WB_OIDC_JWKS_URL | Required for OIDC; local Keycloak certs endpoint for the smoke |
| WB_FIXTURE_STORE | repository `.local/fixtures.json`; synthetic-only directory |
| WB_FIXTURE_PUBLIC_KEY | repository `.local/fixture-public.pem` |
| WB_DATABASE_URL | Secret SQLAlchemy PostgreSQL URL; bootstrap generates local credentials |
| WB_DEPENDENCY_CHECKS | `false` native; Compose `true` probes database with bounded connection time |
| WB_TEMPORAL_ADDRESS | `127.0.0.1:7233` host; `temporal:7233` in Compose |
| WB_TEMPORAL_NAMESPACE | `default`, development only |
| WB_TEMPORAL_TASK_QUEUE | `foundation` |
| WB_S3_ENDPOINT | `http://127.0.0.1:5000`, simulator |
| WB_S3_ACCESS_KEY / WB_S3_SECRET_KEY | Local simulator values; never cloud credentials by default |
| WB_S3_REGION | `ap-south-1`, source metadata/default only; not a residency guarantee |
| WB_S3_BUCKETS | JSON array of quarantine/evidence/report development buckets |
| WB_TELEMETRY_ENABLED | `false` native, `true` Compose |
| WB_OTLP_ENDPOINT | Collector HTTP trace endpoint; no document contents exported |
| WB_EXPOSE_LOCAL_METRICS | `true`; only loopback-exposed local foundation |
| WB_BUILD_REVISION | `working-tree` unless injected at build/runtime |
| POSTGRES_PASSWORD | Generated local-only Compose credential |
| KEYCLOAK_ADMIN_PASSWORD / GRAFANA_ADMIN_PASSWORD | Generated local admin credentials |
| WB_INTEGRATION_DATABASE_URL | Test-only explicit database URL; integration test otherwise skips |

Do not substitute production records into the fixture store or enable real source credentials. Production configuration and full identity/assignment persistence are delivered in later phases.
