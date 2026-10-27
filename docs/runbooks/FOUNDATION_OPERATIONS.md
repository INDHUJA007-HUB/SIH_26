# Foundation operation and diagnostics

Scope: synthetic local development only. Start/stop/check commands are in the getting-started guide. The user approved Docker Desktop installation for local verification; no cloud resources, live messages or regulatory decisions are activated.

## Service not ready

Inspect `docker compose --env-file .env -f infra/compose/compose.yaml ps`. Inspect logs for the failing service only. Do not print `.env`, full tokens or document contents. PostgreSQL must be healthy before migration, migration must exit zero before API, and Temporal must be ready before the worker. Retry safe startup after addressing the cause; do not delete volumes to suppress an error.

## Workflow smoke fails

Check Temporal health and worker task queue `foundation`; inspect the opaque workflow ID in Temporal UI. Confirm matching namespace/task queue and compatible image. The smoke passes reference-only input and returns SYNTHETIC_PLATFORM_OK. It does not demonstrate the future full evidence workflow.

## Telemetry verification

Perform `api-smoke`, open the provisioned Grafana dashboard and inspect request traces in Jaeger. Route/status labels must not contain query strings or raw IDs. Export sanitization removes SQL text, exception events/status descriptions and unknown attributes. Foundation logs use an allowlist, omit raw messages/bodies/headers and carry a bounded request ID. Later official audit/access logs are separate domain functionality.

## Dependency or image finding

Preserve scanner output, identify affected package and fixed version, update the source requirement/lock or image digest, then rerun focused compatibility and security checks. Do not disable scans or ignore all unfixed findings merely to obtain a green badge. Local tooling/sidecars and production API runtime are distinct scopes.

## Generated state and privacy

`.local` and `.env` contain local keys/credentials and are excluded from Git. Synthetic fixture IDs/names are fictional. Do not add real applicant documents to benchmark fixtures. Artifacts contain only synthetic compatibility outputs and operational reports; check before sharing.
