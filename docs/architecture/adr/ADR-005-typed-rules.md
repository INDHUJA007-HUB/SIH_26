# ADR-005: Bounded deterministic rule DSL

Status: accepted engineering baseline for synthetic development, 26 October 2026. Regulatory/procurement approval is separate.

## Decision

Rules use typed inputs, explicit unknowns, units, rounding, dates and sourced interpretation.

## Consequences and validation

No eval, arbitrary SQL, network access or autonomous model policy activation. Draft seeds remain disabled.

## Alternatives and revisit trigger

The more operationally complex alternative is deferred until measured workload, ownership, source contracts or deployment policy requires it. Revisit with a new ADR and migration/rollback evidence; preserve this decision record. The implementation plan records broader options and rationale.
