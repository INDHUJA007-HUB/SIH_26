# ADR-006: Authorized source adapters

Status: accepted engineering baseline for synthetic development, 26 October 2026. Regulatory/procurement approval is separate.

## Decision

Providers expose capability, source mode, authorization, identity/freshness and response provenance.

## Consequences and validation

No live claim before actual onboarding. HTTP timeout and unavailable do not mean mismatch.

## Alternatives and revisit trigger

The more operationally complex alternative is deferred until measured workload, ownership, source contracts or deployment policy requires it. Revisit with a new ADR and migration/rollback evidence; preserve this decision record. The implementation plan records broader options and rationale.
