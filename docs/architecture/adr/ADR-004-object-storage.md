# ADR-004: Version-specific private objects

Status: accepted engineering baseline for synthetic development, 26 October 2026. Regulatory/procurement approval is separate.

## Decision

Metadata pins exact original/derivative versions and hashes.

## Consequences and validation

Moto is a disposable local simulator; real S3 IAM/conditional/version/retention behavior requires cloud tests.

## Alternatives and revisit trigger

The more operationally complex alternative is deferred until measured workload, ownership, source contracts or deployment policy requires it. Revisit with a new ADR and migration/rollback evidence; preserve this decision record. The implementation plan records broader options and rationale.
