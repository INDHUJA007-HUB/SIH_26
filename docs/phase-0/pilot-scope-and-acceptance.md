# Pilot scope and acceptance baseline

First vertical slice: synthetic EoA-style E&T UG institution, cycle 2026–27, one campus, two named rooms, a short website-disclosure video, certificate/date fields, intake/bandwidth declaration and labelled source responses. This category is a development choice, not a claim that the complete EoA process is implemented. Later categories require separate applicability/process validation.

Pilot planning profile: 100 institutions; 1,000 packets/cycle; median 50 pages; 200 simultaneous sessions; 25 requests/second sustained and a short 75 requests/second burst. Separate media quotas and source-rate limits. No national-scale performance claim.

| Scenario | Expected acceptance |
| --- | --- |
| A01 Valid local identity | Own synthetic institution returned |
| A02 No/expired/wrong issuer/audience token | Safe 401; no token/content logged |
| A03 JWT claims admin or another institution | Backend assignment remains authoritative |
| A04 Submitted packet then new upload | Submitted manifest remains unchanged |
| A05 Required evidence absent | Completeness missing; no nonexistent source attempt |
| A06 Issuer HTTP 503 | Source unavailable; owned retry/manual task; no penalty |
| A07 Suspicious/recompressed image | Forensic advisory; source status unchanged |
| A08 Authenticated source conflict | Scoped mismatch with both values/response reference |
| A09 Ambiguous date or cadre rule | Unknown/manual interpretation, never invented result |
| A10 Reviewer corrects OCR | New fact set; original PDF and previous run retained |
| A11 Response changes only requested certificate | Accepted new response and reassessment |
| A12 Response also changes intake | Scope violation and no submission mutation |
| A13 Candidate rule publication | Separate approver; exact hash; historical run unchanged |
| A14 Source simulator returns verified | SIMULATED throughout; excluded from live-success metric |
| A15 Video lacks GPS | Not available, not false location |
| A16 Partial photo shows 12/declares 20 | Visible candidates only; no automatic shortage claim |
| A17 Replayed alert/job | One logical effect; actual attempts retained |
| A18 Document access aborts | Attempt and bytes/abort recorded; no human-reading claim |
| A19 Worker/Temporal outage | Committed outbox resumes safely |
| A20 Native/Compose setup | Bootstrap, authenticated fixture, migration/seed and worker smoke |

A01–A03 and native A20 are Phase 1 acceptance; the other cases are allocated in traceability/backlog and become release gates in their implementation phases. No invented regulatory sign-off or user-study result is included.
