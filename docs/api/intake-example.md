# Phase 2–4 client contract

Base URL: `http://127.0.0.1:8000/api/v1`. The running server publishes the complete DTOs at `/openapi.json` and `/docs`. Use bearer access tokens from the configured issuer. Local synthetic tokens can be produced with `uv run --project backend python -m workbench.tools token --subject <seed subject>`; inspect `--help` for the local token arguments. Never persist a bearer token or signed URL in logs.

1. `GET /me`: obtain current persisted memberships and assurance.
2. `POST /applications`, with `Idempotency-Key`, creates a draft:

```json
{
  "institution_id": "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa",
  "category": "EOA",
  "cycle_start": 2026,
  "programme": "ENGINEERING_AND_TECHNOLOGY",
  "level": "UG",
  "declared_facts": {
    "bandwidth": {"value": 100, "unit": "Mbps", "basis": "institution declaration"}
  },
  "slots": [{"code": "FIRE_CERTIFICATE", "required": true}]
}
```

3. `GET /applications/{id}` returns the revision and slot IDs. `PATCH` requires `expected_revision` and the complete replacement `declared_facts`. It creates another immutable revision.
4. `POST /applications/{id}/upload-sessions`, with `Idempotency-Key`, sends `slot_id`, `filename`, `media_type`, `size_bytes`, lowercase hex `sha256`, and `mode` (`SINGLE` or `MULTIPART`). Optional `parent_version_id` represents a new version in the same slot. The response contains a bounded single PUT grant or multipart count/part size.
5. PUT bytes directly to `grant.url` with every supplied `grant.headers` unchanged. Preserve the `x-amz-version-id` response header. For multipart, request each `/upload-sessions/{id}/parts/{number}` grant and PUT that exact slice; the backend retrieves provider part details at completion.
6. `POST /upload-sessions/{id}/complete`, with `Idempotency-Key` and `{"version_id":"captured-version"}` for single uploads, returns 202 with an evidence ID. Multipart accepts `{}`. A 202 response means quarantine intake, not acceptance. Repeated keys with identical bodies replay the same command receipt.
7. Poll `GET /evidence/{id}` until `ACCEPTED` or `REJECTED`; `SCAN_FAILED` needs retry/operations review. Do not describe quarantine as usable evidence. GET `/evidence/{id}/content` streams accepted originals; `/pages/1` streams an available PNG preview. Add a single `Range: bytes=0-1023` header for original partial reads. HEAD returns authorized metadata without content. Storage keys are excluded from evidence responses.
8. `POST /applications/{id}/submit`, with a new `Idempotency-Key`, sends `expected_revision` and selected `evidence_ids`. Abort unfinished sessions first using `POST /upload-sessions/{id}/abort`. The result includes the submitted revision, manifest SHA and event ID. A submitted packet is immutable.
9. Read `/applications/{id}/revisions`, `/summary`, `/audit-events`, `/tasks`, and `/evidence/{id}/access-events`. Cursor parameters and limits are documented in OpenAPI. Summary source verification remains unimplemented and compliance remains unevaluated.

Command errors include a stable code, status and request ID. 401 means authentication is unavailable/revoked; 403 means authority/assurance is insufficient; 404 hides unavailable resources; 409 covers revision/state/idempotency conflicts; 410 covers expired/aborted uploads; 413 covers configured size limits; 416 covers invalid ranges; 422 covers request schema; 429 covers reserved storage/processing quotas; 503 covers dependency outages.

For a browser client, perform authenticated API fetches with cache disabled and let the download response control content disposition. The API deliberately returns a stream instead of a transferable clean-object URL. An application frontend on another origin needs an explicitly approved CORS/origin configuration; no wildcard credentials policy is enabled here.
