# ADR-012: Versioned retention and audit control

Status: accepted engineering baseline for synthetic development, 26 October 2026. Regulatory/procurement approval is separate.

## Decision

Separate evidence, security logs, temporary files, backups and legal holds with independent checkpoints.

## Consequences and validation

Do not lock every object forever or call a hash chain absolutely immutable. Production retention requires owner approval.

## Alternatives and revisit trigger

The more operationally complex alternative is deferred until measured workload, ownership, source contracts or deployment policy requires it. Revisit with a new ADR and migration/rollback evidence; preserve this decision record. The implementation plan records broader options and rationale.
