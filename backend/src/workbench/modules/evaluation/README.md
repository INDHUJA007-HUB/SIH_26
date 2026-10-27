# evaluation

Pure deterministic evaluator over frozen inputs. No network calls or statutory actions. Implemented in Phase 7.

Boundary: domain code uses standard library/value contracts; application services depend on typed ports. HTTP, SQL, storage and provider details belong to adapters/composition. Cross-module ORM imports are prohibited. The package boundary exists in Phase 1; its future business features are not claimed as implemented.
