# Development setup — Phases 0–4

Repository: `C:\SideQuest\SIH` on this workstation. Commands are relative to the repository so a fresh clone on another machine works without editing code.

## Prerequisites

Git, uv 0.13.4 or newer patched compatible version, Python 3.12 (uv can provide it), Docker Desktop/Engine with Compose. Full stack includes PostgreSQL, Temporal, Moto S3, Keycloak, mail/observability services, API, intake/scan/relay/reconciliation workers, ClamAV and a networkless parser. Allow sufficient RAM/disk and internet for initial image/signature downloads; the user's 16GB Windows machine is the local verification target. This is a development stack.

For the published-image path, only Git and Docker with Compose are required. Python and uv run inside the signed application image.

## Docker-only published images

Clone the repository, open a terminal at its root, and run:

```powershell
.\scripts\container.ps1 up
.\scripts\container.ps1 check
```

On Linux or macOS:

```sh
sh scripts/container.sh up
sh scripts/container.sh check
```

The launcher pulls these GitHub Container Registry packages and then starts the pinned supporting services from `infra/compose/compose.yaml`:

- `ghcr.io/indhuja007-hub/sih_26:latest`
- `ghcr.io/indhuja007-hub/sih_26-parser:latest`

The release workflow publishes an immutable commit-SHA tag beside `latest`, scans every target for HIGH/CRITICAL findings before publication, produces SBOM/provenance attestations and signs each digest. For a repeatable demonstration, set `SIH_RUNTIME_IMAGE` and `SIH_PARSER_IMAGE` to the same commit-SHA release instead of relying on the moving `latest` tag. GHCR packages must be made public once by a repository/package administrator; until then, authenticate with `docker login ghcr.io` using an account allowed to read the packages.

The launcher uses the backend image to create `.env` and `.local/` on first use, without putting real secrets in the image. It preserves existing local state. The distribution override removes local build definitions and starts the same Compose topology with the downloaded images. Stop it without deleting volumes:

```powershell
.\scripts\container.ps1 stop
```

## Windows

From PowerShell in the repository:

```powershell
.\scripts\dev.ps1 up
.\scripts\dev.ps1 check
```

Bootstrap generates `.env` with random local database/admin credentials, an RSA key pair and synthetic fixtures in `.local/`. Existing credentials/keys are preserved. Never commit these files. It copies all 22 research records as disabled drafts. Database seeding is idempotent.

Native API only, without containers:

```powershell
.\scripts\dev.ps1 native
```

In another terminal:

```powershell
uv run --project backend python -m workbench.tools api-smoke
```

The smoke obtains its local token internally and prints only the synthetic response. The optional `token` command prints a ten-minute local fixture token for manual development; do not paste tokens into issue reports or logs. Native readiness explicitly identifies its no-dependency-checks profile. It does not prove PostgreSQL or source integration.

## Linux/macOS

```sh
sh scripts/dev.sh up
sh scripts/dev.sh check
```

Windows per-user Docker detection is handled by the PowerShell script. New terminals normally receive Docker's installed PATH entry.

If Docker Desktop's build network stalls during package downloads while normal containers can download, the Windows script supports a build-only fallback: set `$env:WB_BUILD_NETWORK='host'` before `up`. It passes Docker's explicit host-network build entitlement; runtime service networks and the parser's disabled network are unchanged. Unset the variable after the build if normal build networking works again. Dependency hashes remain locked in both paths. See uv's [documented HTTP controls](https://docs.astral.sh/uv/configuration/environment/) for timeout configuration.

## Local endpoints

| Component | Address | Purpose |
| --- | --- | --- |
| API/OpenAPI | http://127.0.0.1:8000/docs | Phase 2–4 identity/application/evidence contract |
| Health/version | `/health/live`, `/health/ready`, `/version` | No secret configuration disclosed |
| Fixture | `/api/v1/foundation/fixture` | Authenticated own synthetic institution |
| Temporal UI | http://127.0.0.1:8233 | Development workflow history |
| Keycloak | http://127.0.0.1:8081 | Development identity realm |
| Mailpit | http://127.0.0.1:8025 | Local mail sink; no real outbound recipients |
| Grafana | http://127.0.0.1:3000 | Provisioned foundation request/error dashboard |
| Jaeger | http://127.0.0.1:16686 | Request/SQL/worker trace inspection |
| Prometheus | http://127.0.0.1:9090 | Local route/status counters |
| S3 simulator | http://127.0.0.1:5000 | Disposable development bucket API |

Grafana/Keycloak local admin username: `local-admin`; generated passwords are in your untracked `.env`. Keycloak synthetic fixture users are defined in the clearly labelled imported realm. No production identity or real data is supported.

## Checks

```powershell
cd backend
uv sync --frozen --group dev --group spikes
uv run ruff check src tests tools migrations
uv run ruff format --check src tests tools migrations
uv run mypy
uv run python tools/check_architecture.py
uv run python tools/check_repository.py
uv run python tools/check_secrets.py
uv run pytest --cov=workbench --cov-report=xml
uv run python tools/run_spikes.py --s3
uv run python tools/check_oidc.py
```

For the PostgreSQL integration test set `WB_INTEGRATION_DATABASE_URL` to the same local URL as `WB_DATABASE_URL` without printing either. A missing integration URL results in an explicit skip. On Linux use the relevant shell environment syntax. CI has separate native, PostgreSQL and Compose jobs.

The new harness uses the generated dedicated runtime URLs and uses the integration flag to opt into the local database. Set `WB_FILE_INTEGRATION=1` to run actual ClamAV/parser/S3/Temporal tests after starting the full stack. Set `WB_CHAOS_INTEGRATION=1` only in a disposable local development session to include service-stop/recovery probes. See [Phase 2–4 verification](PHASE_2_4_VERIFICATION.md) and [implementation/runbooks](PHASE_2_4_IMPLEMENTATION.md).

## Stop and safe cleanup

```powershell
.\scripts\dev.ps1 stop
```

Stop removes only containers/networks in the fixed `sih-foundation` Compose project. It preserves named volumes, generated keys, local credentials and fixtures. No script automatically removes volumes or recursively deletes the repository. Moto/Jaeger contents are disposable development state and are not production evidence. To reset databases, first inspect the exact project-labelled volumes, back up anything needed and explicitly approve that reset; do not use broad Docker pruning commands.

## Troubleshooting

- Docker unavailable: open Docker Desktop and confirm the Linux engine is running; the Windows user may need to finish a first-run prompt or restart after prerequisites change.
- Port conflict: inspect the owning process; do not kill another user's service. Adjust the documented local mapping/settings together.
- Database authentication failure: `.env` credentials and an existing PostgreSQL volume must match. Bootstrap intentionally preserves both rather than silently resetting data.
- Frozen lock failure: use the committed uv.lock and Python 3.12; review intentional dependency changes through CI.
- Readiness 503: inspect service/container health without dumping `.env` or raw signed documents.
- OCR model download blocked: the optional spike requires approved public model access; retain a NOT_RUN/FAILED result rather than claiming support.
- Windows test temporary directory: tests create uniquely named directories under repository `.local/pytest/`, avoiding inaccessible global temporary folders.

Persisted domain authorization and evidence intake are implemented through Phase 4. Automated regulatory rule execution and official decisions remain later-phase work, as reported by `/api/v1/capabilities`.
