# Data classification and threat model

## Data classes

| Class | Examples | Access/retention baseline |
| --- | --- | --- |
| PUBLIC_RESEARCH | Handbook copies, public sources, implementation docs | Repository; third-party rights retained; no real applicant personal data |
| SYNTHETIC_FIXTURE | Fictional identities, institution names, synthetic rule scenarios | Development only; reset by explicit local operation |
| CONFIDENTIAL_EVIDENCE | Future originals, extracted personal fields, signed records | Approved purpose; institution/assignment checks; encrypted private storage; approved case-retention policy |
| SECURITY_SECRET | Generated local keys, provider tokens, database credentials | .local/.env excluded; production secret manager later; never log/export |
| AUDIT_ACCESS | Future actors/actions/object versions and access results | Restricted role; independent checkpoints; policy-specific retention |
| OPERATIONAL | Content-free route/status/timing, workflow types | Redacted before transport; bounded local metrics; separate from regulatory audit |
| BACKUP_HOLD | Recovery copies/legal holds | Class-specific retention and deletion/restore policy |

## Threat register

| ID | Threat/boundary | Control | Test/phase |
| --- | --- | --- | --- |
| TH-01 | Client-selected institution/role | Server-side subject directory now; case assignments/RLS later | Token-role forgery test; Phase 2 full BOLA/BOPLA |
| TH-02 | Forged/expired/untrusted token | RS256 allowlist, issuer/audience/required claims, safe 401 | Foundation API tests |
| TH-03 | Fixture mode promoted to real environment | Config rejects nonlocal fixture and all staging/production foundation use | Config tests |
| TH-04 | Credentials/content in logs/traces | Allowlisted fields; drop raw messages, SQL, events and status descriptions | Telemetry tests; collector transport |
| TH-05 | Malicious PDFs/codecs/decompression | Quarantine, bounded isolated worker, fixed tools | Phase 4; no file upload API exists now |
| TH-06 | Document URL SSRF/metadata access | Allowlisted connector egress; DNS/redirect/IP controls | Phase 8; no arbitrary fetch API now |
| TH-07 | Retry/dual-write loss | Domain transaction/outbox and idempotent activities | Phase 3/5; foundation workflow smoke only |
| TH-08 | Self-approved or ambiguous rule | Disabled seed constraints; distinct approval gate later | Seed constraints now; Phase 12 governance |
| TH-09 | Shared dashboard/admin exposure | Loopback binds, generated local admin passwords | Compose structural/runtime checks |
| TH-10 | Dependency/image compromise | Lock file/digests, scanning, signed release/SBOM, action SHA pins | CI/release pipelines |
| TH-11 | Deletion conflicts with holds/backups | Approved retention and reconciliation policy | Phase 14/15; no real-data purge capability now |
| TH-12 | Test data/model leakage and inflated quality | Institution/template split, manifest, label simulator | Test strategy; Phase 13 |

Residual gates: no live source rights, no production policy approval, no independent security assessment, and no completed recovery drill. These do not authorize dangerous demo behavior. Native fixture keys are intentionally unencrypted local-only developer material; protect the Windows account and never use them for real users or deployment.
