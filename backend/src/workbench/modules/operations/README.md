# operations

Health, safe diagnostics, reconciliation, feature capability and provider state. Phase 1 supplies the foundation health/capability endpoints.

Boundary: domain code uses standard library/value contracts; application services depend on typed ports. HTTP, SQL, storage and provider details belong to adapters/composition. Cross-module ORM imports are prohibited. The package boundary exists in Phase 1; its future business features are not claimed as implemented.
