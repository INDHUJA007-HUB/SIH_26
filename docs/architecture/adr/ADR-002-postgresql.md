# ADR-002: PostgreSQL domain authority

Status: accepted engineering baseline for synthetic development, 26 October 2026. Regulatory/procurement approval is separate.

## Decision

PostgreSQL owns typed domain records, constraints and transactional metadata. Objects own bytes.

## Consequences and validation

Phase 1 tables are synthetic only; RLS and case assignments are Phase 2. JSON fixtures are local adapters.

## Alternatives and revisit trigger

The more operationally complex alternative is deferred until measured workload, ownership, source contracts or deployment policy requires it. Revisit with a new ADR and migration/rollback evidence; preserve this decision record. The implementation plan records broader options and rationale.
