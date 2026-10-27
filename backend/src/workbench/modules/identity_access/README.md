# identity_access

Actor identity, scoped assignments, and authorization. Phase 1 provides token verification and a synthetic server-side directory only; full permissions/RLS are Phase 2.

Boundary: domain code uses standard library/value contracts; application services depend on typed ports. HTTP, SQL, storage and provider details belong to adapters/composition. Cross-module ORM imports are prohibited. The package boundary exists in Phase 1; its future business features are not claimed as implemented.
