# ADR-007: Separate untrusted processing

Status: accepted engineering baseline for synthetic development, 26 October 2026. Regulatory/procurement approval is separate.

## Decision

Use bounded scan/PDF/OCR/media containers with scoped credentials and no general internet.

## Consequences and validation

Connector egress is separate. Request handlers never decode untrusted PDFs/videos.

## Alternatives and revisit trigger

The more operationally complex alternative is deferred until measured workload, ownership, source contracts or deployment policy requires it. Revisit with a new ADR and migration/rollback evidence; preserve this decision record. The implementation plan records broader options and rationale.
