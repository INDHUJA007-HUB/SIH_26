# ADR-009: ECS reference deployment

Status: accepted engineering baseline for synthetic development, 26 October 2026. Regulatory/procurement approval is separate.

## Decision

AWS Mumbai reference: private ECS, RDS, S3/KMS, scoped secrets and independent archive.

## Consequences and validation

Region/features/procurement are gates. Kubernetes/service mesh requires a demonstrated workload or platform mandate.

## Alternatives and revisit trigger

The more operationally complex alternative is deferred until measured workload, ownership, source contracts or deployment policy requires it. Revisit with a new ADR and migration/rollback evidence; preserve this decision record. The implementation plan records broader options and rationale.
