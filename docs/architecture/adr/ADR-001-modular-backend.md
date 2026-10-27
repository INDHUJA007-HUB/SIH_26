# ADR-001: Modular backend before business microservices

Status: accepted engineering baseline for synthetic development, 26 October 2026. Regulatory/procurement approval is separate.

## Decision

Typed domain modules share transactional consistency. Processing/trust zones use separate workers.

## Consequences and validation

Split only for measured contention, independently owned releases or a security boundary.

## Alternatives and revisit trigger

The more operationally complex alternative is deferred until measured workload, ownership, source contracts or deployment policy requires it. Revisit with a new ADR and migration/rollback evidence; preserve this decision record. The implementation plan records broader options and rationale.
