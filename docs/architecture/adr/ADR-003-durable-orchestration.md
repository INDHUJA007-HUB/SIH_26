# ADR-003: Temporal plus transactional outbox

Status: accepted engineering baseline for synthetic development, 26 October 2026. Regulatory/procurement approval is separate.

## Decision

Temporal owns durable waits/work; committed outbox connects domain transactions safely.

## Consequences and validation

Phase 1 proves a reference-only workflow; business retries/outbox arrive in Phases 3/5. No Redis/Celery dual orchestration.

## Alternatives and revisit trigger

The more operationally complex alternative is deferred until measured workload, ownership, source contracts or deployment policy requires it. Revisit with a new ADR and migration/rollback evidence; preserve this decision record. The implementation plan records broader options and rationale.
