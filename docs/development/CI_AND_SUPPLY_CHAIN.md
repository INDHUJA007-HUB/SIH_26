# CI, release, and review controls

`quality.yml`: pinned actions, Python 3.12/locked dependencies, Ubuntu/Windows lint/types/tests/import boundaries, PostgreSQL migration/drift/idempotent seed integration, complete Compose smoke and local OIDC verification.

`security.yml`: high-risk credential-format scan, pip-audit report, CycloneDX SBOM, image build and HIGH/CRITICAL Trivy gate. Vulnerabilities are fixed where available. A justified exception must name package/CVE, affected scope, mitigation, approver, expiry and tracking issue; no blanket ignore list is installed.

`release.yml`: main-branch and manual publication of separate runtime and parser GHCR images. It scans each candidate before push, publishes `latest` plus an immutable commit tag, signs the pushed digest with keyless Cosign, and emits build provenance/SBOM attestations. Package visibility is a GitHub administrative setting and must be made public before anonymous pulls. Production deployment is not implemented here.

`cloud-identity.yml`: manual, protected `development-cloud` environment, short-lived GitHub OIDC role, read-only STS identity check. Requires owner-provided AWS_ROLE_ARN and a narrowly scoped AWS trust policy matching this repository/environment. It provisions no resources and uses no permanent AWS key.

Proposed repository settings: protect main; require reviewed PRs and quality/security checks; disallow force-push/deletion; restrict environment deployments; add actual code-owner teams; require separate policy approval for regulatory changes. These are documented proposals, not silently changed GitHub account settings. Forked PR workflows must not receive deployment secrets/write credentials.

Image digests were resolved against official registries and are checked structurally. Dependency versions/hashes live in uv.lock. Refresh locks/digests through a reviewed PR, rerun compatibility/security/runtime checks, and retain prior approved versions for rollback. The optional OCR spike has its own pinned reproducibility record after execution because heavy inference dependencies are isolated from the API image.

Phase 4 adds separate runtime/parser image scan targets and actual quarantined-file acceptance tests in the Compose job. Container builds export exact, hashed requirements from `uv.lock`, retrieve compatible PyPI wheels with an origin/size/SHA-256 check, then install offline with pip's required-hash validation. The bounded standard-library downloader avoids a download-stream stall observed in this Windows Docker environment; dependency versions and trust checks are unchanged. Source package archives and alternate unpinned versions are not fallback paths. Native developer environments still use frozen uv sync.
