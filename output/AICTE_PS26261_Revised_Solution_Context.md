# AICTE PS26261: Revised Solution Context and Build Specification

**Research cut-off:** 26 October 2026, India time. **Version:** 3.0, research and proposed specification. **Implementation status:** no implementation of the team's product was supplied or audited in this workspace. Every product capability below is proposed unless explicitly identified as an observed competitor capability. No benchmark has been run for the proposed product.

## 1. The decision: build a governed evidence and rectification workbench

Position the solution as **AICTE Evidence and Compliance Workbench**, a proposed name, rather than another generic AI document-verification portal. Its purpose is to help an authorized reviewer answer five questions: what is required for this application; what evidence supports each claim; what remains uncertain; what correction is permitted; and what changed between reviews.

The most defensible differentiation is the complete chain from **a sourced amendment to a reviewed rule change, an explained finding, a permitted correction, and a reproducible review record**. OCR, dashboards, QR reading, digital-signature checks, hash chains, and rule-impact screens already appear in public implementations. They are useful capabilities, but weak standalone uniqueness claims.

Build three demonstrations exceptionally well:

1. **Regulatory change without rewriting history.** Resolve rules for the correct cycle, compare a candidate amendment against frozen application facts, require a second authorized approver, and preserve the earlier evaluation.
2. **Correction without uncontrolled editing.** Issue a scoped request under an allowed process stage, receive a new evidence version, show its diff, and re-evaluate affected checks while preserving the original submission.
3. **Uncertainty without an accusation.** A source outage remains a source problem; a suspicious photo remains a forensic concern; neither automatically becomes an issuer mismatch or an adverse regulatory decision.

A useful pitch is: “We connect each preliminary finding to the applicable rule and evidence, show what can be corrected, and preserve what changed for the next reviewer. AI assists extraction and triage; competent AICTE authorities retain scrutiny, inspection and decisions.” This is a proposed positioning statement, not a claim of deployment or official endorsement.

### 1.1 What changes from the previous research

The 36-page uploaded research is a strong starting inventory, but it expressly says that it did not open the handbook or amendment PDFs and did not inspect competitor code beyond READMEs. This revision examines the uploaded 231-page handbook, visually checks consequential tables, reads the seven additions, retrieves amendment documents, and inspects selected competitor source files at fixed commits.

Several earlier recommendations need correction themselves. Most significantly, Pramana already implements rule-impact comparison and numerical readiness advice. The uploaded handbook does not visually support the previous report's asserted minus-one adjustment to the UG Professor formula. Annexure 14 is a land/building authority table, not a fire-authority directory. The previous rule that two medium forensic signals can produce “Mismatch Detected” also conflicts with the seven-additions image's requirement to keep forensic flags separate from source-comparison statuses.

**Do not carry forward the earlier “first”, “nobody else”, “zero false alarms”, “live government verification”, “immutable blockchain”, or guaranteed time-saving claims.** Replace each with a scoped, evidence-backed statement or a clearly labelled target.

## 2. Evidence standard and research boundaries

### 2.1 Labels used throughout

| Label | Meaning | What it permits |
| --- | --- | --- |
| V-U | Verified in an uploaded source, including relevant visual inspection | A claim about that specific supplied document |
| V-P | Verified on an accessible primary publisher or official documentation page | A scoped factual claim, with the source and retrieval date |
| V-M | Text verified in an apparent AICTE-issued document hosted on a public mirror | Cite the document and mirror; do not imply authenticated publisher download or complete currency |
| C-S | Competitor source code inspected at a fixed commit | Claim the inspected implementation exists; do not imply it was executed successfully |
| C-R | Competitor README or demo claim only | Attribute it to the author; do not present performance as independently measured |
| P | Proposed design, target, policy or estimate | Suitable for a specification or roadmap; not an achieved result |
| O | Open, ambiguous, unavailable or not independently established | No automated adverse inference based on this claim |

Source-content verification, legal applicability, operational approval, and successful implementation are separate properties. A correctly transcribed number is not automatically the right number for every institution or cycle.

### 2.2 Inputs examined

| Input | Scope of examination | Main consequence |
| --- | --- | --- |
| Competitive research PDF, prepared 25 October 2026 | All 36 pages, including C-01 through C-32, U-01 through U-12, evaluation, source list and test vectors | Retain its governance direction; correct unverified norms and overstated novelty |
| Uploaded APH 2024-25 to 2026-27 | 231-page file; targeted analysis across approval processes, standard norms, penalties, document lists, infrastructure, faculty, competent authorities, disclosures and Affidavit 2 | Use printed page and physical PDF page together; qualify table ambiguities |
| Seven-additions image | All seven numbered additions transcribed and mapped into acceptance criteria | Treat them as actual scope requirements, not optional notes |
| 2025-26 addendum mirror | Located within a 261-page combined handbook/addendum file; amendment cover at PDF p.234; substantive pages include PDF pp.257-260 | Separate the document's identity from its misleading “26-27” URL filename |
| 2026-27 addendum mirror | 21-page file, including side-by-side modified clauses | Verify selected changes; preserve mirror provenance and unresolved applicability |
| Competitors | Five named repositories/public surfaces; selected backend, UI and test files for three | Distinguish code evidence, claims and untested behavior |

The uploaded handbook has a physical PDF page offset of 16 for the cited Arabic-numbered pages: printed 95 is PDF 111, for example. Never use a printed page from one copy as the physical page of another copy.

### 2.3 Currency limitation that matters

On this research run, the AICTE home page returned a maintenance page, approval pages returned access errors, and the official SIH problem-statement route could not be retrieved. The problem brief is therefore checked against the public mirror used by the previous report, not certified against a currently accessible official listing. Its 28 October 2026 deadline and idea count are **O: unofficial mirror information**, and are not used as confirmed planning facts. [S01, S02, S03]

The 2025-26 addendum's existence is corroborated by AICTE's own public announcement; its detailed text and the 2026-27 text were read from mirrors. This report verifies selected amendment content, **not the absence of subsequent circulars, court directions, portal instructions, or a later consolidated version as of 26 October 2026**. A production rule pack requires an authorized regulatory owner to establish the complete applicable document set. [S04, S05, S06]

The full earlier v2.0 product specification and a product repository were not attached. Findings about defects in that older implementation remain statements in the supplied research, not newly observed defects in the team's code.

## 3. Regulatory findings and corrections

### 3.1 Verified handbook content to encode carefully

The following findings are **V-U** and cite the supplied handbook [U02]. They establish what the supplied base document says. Amendment resolution and institution applicability still precede enforcement.

| Topic | Checked location | Correct interpretation and design consequence |
| --- | --- | --- |
| EoA based on self-disclosure | Annexure 2.1, printed 81 / PDF 97 | Requirements include Affidavit 2, applicable portal payment receipt, occupancy/completion/building document, conditional structural certificate, valid fire certificate, satellite map and previous-year audited accounts. Do not impose a new-institution checklist on every EoA |
| Affidavit 2 formalities | Annexure 2.1(i), printed 81 / PDF 97; format printed 186 / PDF 202 | The EoA list specifies the Chairman/Secretary's digital signature, Rs.100 e-stamp and sworn-before formalities. Verify declarant, application and actual uploads; an applicant's DSC does not authenticate the original issuer of every annexed certificate |
| Structural certificate trigger | Clause 6.17(h), printed 57 / PDF 73; Annexure 2.1(iv), printed 81 / PDF 97 | Count building age from the completion certificate. A registered Structural Engineer issues the certificate; the base text provides five-year validity. Calendar anniversaries and the applicable review date must be explicit |
| Older government buildings | Annexure 2.1, printed 81 / PDF 97 | A competent-authority letter is a conditional documentary alternative where specified government buildings are older than 50 years and original documents cannot be submitted. This is not a blanket exemption from structural or fire safety |
| Fire safety | Clause 6.17(i), printed 57 / PDF 73 | A valid certificate from the competent authority is required. The handbook does not establish a universal five-year fire-NOC lifetime |
| Annexure 14 scope | Printed 163 / PDF 179 onward | Columns concern land use, site plan, building plan and occupation certificate. Build a separate fire-authority mapping from authorized state sources; do not reuse this table as a fire directory |
| Computing facilities | Annexure 4.1, printed 92 / PDF 108 | Ratios depend on programme and level. Each department has a separate lab with at least 20 computers. Library, administrative and faculty computers are additional to student provision |
| Printers and plotter | Annexure 4.1 notes 3-4, printed 92 / PDF 108 | Minimum printers are 5% of PCs/laptops. The A1 colour printer/plotter provision is specific to Planning |
| Internet bandwidth | Annexure 4.1 note 5, printed 92 / PDF 108 | Intake up to 300: 100 Mbps; 301-600: 300 Mbps; 601-900: 500 Mbps; above 900: printed as 1 Gbps tier. Normalize the apparent “1Gbpa” typo with an explicit transcription note |
| Faculty basis | Annexure 5.1-5.3, printed 95-96 / PDF 111-112 | S is the sum of students according to approved intake for all years. Distinguish that from annual intake and actual admissions |
| Low-admission relaxation | Printed 96 / PDF 112 | The text gives a 25% faculty reduction when three-year average admissions are at most 50% of average sanctioned intake. Programme scope, rounding and counting require an approved interpretation; missing history cannot establish eligibility |
| Room sizes | Annexure 3 tables, including printed 87-89 / PDF 103-105 | A universal 66 sq.m classroom or laboratory rule is wrong. Room type, programme, level, capacity and footnotes matter; Planning has different examples |
| Mandatory disclosures | Clause 6.32; Annexure 18, printed 180-184 / PDF 196-200 | Public website disclosure is a real obligation. Website inconsistencies can support a separate disclosure finding; they do not establish issuer authentication or automatic rejection |
| Short infrastructure video | Annexure 18.15(xviii), printed 184 / PDF 200 | The website provision calls for a 1-2 minute infrastructure/facilities video. This differs from EVC evidence |
| EVC recording | Clause 1.9(f)-(g), printed 8 / PDF 24; Annexure 1.2(ix), printed 79 / PDF 95 | The base text describes at least 30 minutes in the relevant online/physical EVC contexts, with contextual publication and recording instructions. Do not apply a 30-minute rule to every video upload |
| Rectification scope | Clause 1.8(f)-(g), printed 7 / PDF 23 | Re-scrutiny concerns deficiencies identified by scrutiny. This supports a controlled evidence-response workflow, not unrestricted amendment of a submitted application |

### 3.2 Base faculty and computer ratios

The ratio transcription below is verified in the uploaded tables. It is an input catalogue, not a declaration that every row is operationally approved for every 2026-27 case. [U02]

| Programme | UG faculty:student | PG faculty:student | Student computing ratio, UG / PG |
| --- | --- | --- | --- |
| Engineering and Technology | 1:20 | 1:15 | 1:6 / 1:4 |
| Planning | 1:16 | 1:10 | 1:6 / 1:4 |
| Applied Arts and Crafts | 1:15 | 1:15 | 1:6 / 1:4 |
| Design | 1:15 | 1:15 | 1:6 / 1:4 |
| Hotel Management and Catering Technology | 1:20 | 1:12 | 1:6 / no PG entry in this computing table |
| Computer Applications | 1:25 | MCA 1:20 | 1:10 / 1:4 |
| Management | 1:25 | MBA/PGDM 1:20 | 1:10 / 1:6 |

The listed Diploma faculty ratio is 1:25. The computing table separately includes Diploma entries for relevant streams; do not infer Diploma coverage from the UG column above.

**A consequential ambiguity:** the rendered UG faculty table lists Principal = 1, the three cadre expressions proportional to 1:2:6, and total = S/FSR. The three cadre expressions already sum to S/FSR. Unlike the earlier research's assertion, the displayed Professor expression does **not** show a minus one. The Diploma table also shows a total and component expression that do not straightforwardly reconcile with its HOD column. The PG table combines ratio expressions and notes that require interpretation. [U02, printed 95-96 / PDF 111-112]

Therefore do not label the previous `Professor = S/(FSR*9)-1` proposal as a verified transcription. Store the printed expression, the inconsistency, and a separately approved operational interpretation. Until resolved, show a total-ratio planning estimate and mark cadre allocation **O: manual interpretation required**. Never subtract the Principal silently or claim the old worked examples are authoritative. This is an excellent example of why rule governance is useful.

### 3.3 Verified amendment text, with provenance limits

**2025-26, V-M:** the mirrored addendum deletes clause 6.14(d)(iii), and adds PoP material to Annexure 5. Its Engineering and Technology provision caps PoP at 20% of required faculty strength, with 5% reserved for women PoP/Associate/Assistant PoP on a regular basis; other programmes retain prevailing norms. Printed pp.20-23 are combined-file PDF pp.257-260. This does not prove that every adjunct provision in every programme was abolished. Preserve the reservation's wording and obtain an authorized interpretation of its denominator and rounding. [S04, S05]

**2026-27, V-M:** clause 2.9 distinguishes international-student supernumerary seats: E&T Diploma/UG 15%, E&T PG 25%, other listed programmes at all levels 25%; NIL deficiency on self-disclosure remains a condition. Modified clause 1.3.3(b) changes “Non-Technical” to “Technical” institutions; this textual edit alone does not settle all BBA/BMS/BCA approval obligations. Committee definitions move constitution to the Council and include physical/online/hybrid EVC. Intake/course changes also acquire programme-classification conditions. The addendum separates essential institutional requirements from desirable DPDP-related measures. Its experiential-learning table and concept note differ on the direction of the 50% condition; leave that interpretation open. [S06, PDF pp.2-8, 14-15, 19-20]

Do not translate these scoped amendments into global constants such as “all foreign seats = 25%”, “all UG management programmes exempt”, or “DPDP compliance is optional”. Statutory privacy obligations arise independently of a handbook's desirable-requirements heading.

### 3.4 Rule activation policy

Each candidate rule must pass four gates: source text checked; scope and ambiguity resolved; software behavior tested; authorized policy approval recorded. Use states `DRAFT`, `SOURCE_CHECKED`, `INTERPRETATION_PENDING`, `TESTED`, `PUBLISHED`, `SUPERSEDED`. A mirror-derived rule may be demonstrated with a provenance badge; production publication requires the regulatory owner's acceptance of that source and its currency.

Deadlines, fee amounts, penalty thresholds, relaxation boundaries, external lookup formats, and programme exemptions must never come from model memory. In particular, the previous broad 10% deficiency thresholds are not activated by this report. The registry marks them open until the exact clause, scope, measure and consequence are captured.

## 4. Revised product context

### 4.1 Users, jobs and constraints

An institution representative prepares a packet, sees missing evidence, obtains a neutral validation report, and responds to permitted requests. A scrutiny officer checks evidence and source responses, corrects extraction errors with reasons, records an observation, and routes a case. A supervisor handles escalation and any required second approval. A rules author proposes changes; a separate rules approver publishes them. An auditor can inspect access and decision history within an authorized scope.

AICTE's existing portal remains the system of record. The workbench is an integration layer for preliminary scrutiny, evidence handling and review assistance. Its value must be tested against the current portal workflow, not against a fictional paper-only baseline. An AICTE-generated public deficiency report already shows portal-generated deficiency reporting and submission-lock declarations. [S07]

### 4.2 The complete evidence model

Represent an application as a collection of claims rather than a folder with one risk score. Examples are: an identified building has a valid fire certificate; a course has a specified approved intake; the current faculty roster contains a given number of eligible individuals; a declared laboratory has evidence that a reviewer can inspect.

Each claim links to one or more document versions, extracted fields, historical records, issuer attempts, applicable rules, and human observations. These relationships form a provenance graph; a relational implementation is sufficient initially. A graph database is not necessary for the MVP.

Evidence is multi-dimensional. A signed certificate can be expired. A source-confirmed document can coexist with an unresolved forensic concern in a different part of the packet. A complete packet can contain an unverified claim. A readable photograph does not prove ownership or total inventory. A historical record can be authoritative for an earlier cycle while being stale for the current one.

### 4.3 Measurable value hypotheses

The proposed hypotheses are fewer repeated checks, earlier correction of missing or expired evidence, reduced reviewer uncertainty, and reproducible application of approved rules. Measure these through review time, decision correctness, repeat requests, evidence coverage, source resolution and false-positive burden. None is an achieved impact claim yet.

## 5. Requirements and deliverable coverage

The following is a working decomposition of the accessible brief mirror and uploaded research. It is not a replacement for the official PS text. [S03, U01]

| Deliverable | Required behavior | Reviewable proof |
| --- | --- | --- |
| Application intake and institutional history | Category-specific checklist; authorized history of EoA, programmes/intake, faculty, accreditation, deficiencies, TER and earlier applications | Category routing and a historical-record comparison, with synthetic provenance badges |
| Document processing | Classify; read digital or scanned documents; extract fields with page regions and confidence; identify omissions, expiry and inconsistencies | Side-by-side source page and extracted values; low-confidence correction workflow |
| Anomaly assistance | Explain potential edits, reuse or contradictions as preliminary indicators | Matched evidence, detector limitations and a human review task |
| Source verification | Authorized issuer/portal/signed-record methods; source, timestamp and result; unavailable/inconclusive fallback | Six statuses, retry history and a visible simulation label |
| Compliance assistance | Applicable handbook and instruction checks; photos, videos, plans and certificates; CV where feasible | A sourced finding and at least one demonstrated advisory infrastructure comparison |
| Reports and alerts | Structured findings and permitted rectification; actionable alerts | Officer/applicant report variants; scoped response and alert audit event |
| Dashboard and safeguards | Status, deficiencies, verification, unresolved discrepancies, pending actions, audit history, access protection and human decisions | Working screens backed by stored events and enforced permissions |

The evaluation plan separately covers the brief's eight metric categories. Security, document-access logging and retention are part of the core deliverable, not later decorative features.

## 6. Status semantics and controlled workflow

### 6.1 Three separate dimensions, plus compliance and workflow

| Dimension | Values | Rules for use |
| --- | --- | --- |
| Completeness | COMPLETE, MISSING, INCOMPLETE, NOT_APPLICABLE | A missing required document has no document-verification result; the requirement remains visible |
| Source verification | VERIFIED, MISMATCH_DETECTED, EXPIRED, VERIFICATION_PENDING, SOURCE_UNAVAILABLE, MANUAL_REVIEW_REQUIRED | Results belong to a specific evidence version, claim and attempt, with source and method |
| Forensic concern | NONE_OBSERVED, FLAGGED, INCONCLUSIVE, REVIEWED_BENIGN, REVIEWED_ESCALATE | Detector outputs and human disposition; no automatic conversion into source mismatch |
| Document validity | VALID_ON_REVIEW_DATE, EXPIRED_ON_REVIEW_DATE, UNKNOWN | A date assessment can be made without claiming issuer authentication; preserve the date source and policy |
| Compliance evaluation | PASS, POTENTIAL_DEFICIENCY, NOT_EVALUABLE, NOT_APPLICABLE | Scoped rule evaluation; not an approval or rejection |
| Workflow | DRAFT, SUBMITTED, SCREENED, OFFICER_REVIEW, AWAITING_RESPONSE, RESPONSE_SUBMITTED, REASSESSMENT, READY_FOR_AUTHORITY, CLOSED | State transitions require permissions and process authority |

The six verification labels follow the accessible brief mirror. The extra dimensions and exact internal identifiers are **P**. An unsigned document's date assessment belongs to document validity; its source status can remain pending. Use the six-status EXPIRED outcome when the mapped verification method supports it, such as a matched issuer record or an issuer-bound signed payload, and record that method. A cryptographic check can establish integrity of signed bytes, but issuer identity/authority and claim coverage still need binding. [S03, S12]

Examples:

- No fire certificate: completeness MISSING; verification null; compliance NOT_EVALUABLE or a missing-evidence finding; applicant task if permitted.
- A valid, readable scan with no EXIF: completeness COMPLETE; no forensic accusation from EXIF absence; source verification remains whatever the actual source check supports.
- Issuer HTTP 503: SOURCE_UNAVAILABLE; a timed manual-confirmation task; no penalty against the institution because of the outage.
- Altered-looking image with two suspicious signals: FLAGGED; officer review; source verification unchanged.
- Authorized issuer record conflicts with a confidently matched certificate field: MISMATCH_DETECTED for that source comparison, with both values and the response reference.
- Signed, authentic certificate whose date is out of validity: show integrity passed and EXPIRED together; preserve the evidence properties rather than flattening them into “fake”.

Do not collapse all dimensions into the earlier precedence chain. The application header should say “2 missing; 1 source mismatch; 1 expired; 2 sources unavailable; 3 forensic concerns; 4 officer tasks”. A summary “Ready for review” requires completed required checks or explicitly accepted unresolved items, not a blanket “Verified institution” badge.

### 6.2 Rectification is a permissioned process

The base handbook allows deficiency handling and scoped re-scrutiny, while public portal-generated declarations warn against general subsequent editing. These are not contradictory if the application is immutable and responses are separately authorized. [U02, clause 1.8(f)-(g); S07]

Before submission, draft edits are allowed. After submission, freeze the submitted application and evidence manifest. An officer may open a response window only if an approved `process_policy` allows that action for the category and stage. Store its authority, request scope, deadline, allowed fields/document slots, number of rounds and initiating officer. Product defaults do not create statutory rights.

A response adds a version; it never overwrites the original. Changes outside the allowed scope are rejected or quarantined for officer consideration. The new report distinguishes resolved, unchanged, newly observed and no-longer-evaluable findings. Re-evaluate dependency-linked checks, and run a whole-packet consistency check so an indirect effect is not missed. System-generated findings can be drafted; official notices, adverse actions and statutory decisions follow the competent authority's workflow.

## 7. Technical specification

### 7.1 Architecture and boundaries

Use a modular backend with asynchronous evidence jobs, an immutable facts layer, and a deterministic evaluator. Suggested components are a React/TypeScript review interface, a Python/FastAPI service, PostgreSQL, encrypted object storage, and a job queue with durable retries. These are **P**, selected for development practicality; pin actual versions only after testing the chosen stack.

The processing chain is: authenticated upload -> quarantine -> safe parsing and OCR -> versioned extracted facts -> claim/evidence reconciliation -> source-verification attempts -> resolved rule evaluation -> review workspace -> report/response workflow -> audit and reproducibility export. Photos, videos and plans are evidence-processing branches. Rule publication is a separate, restricted administrative workflow.

External source calls are not made from inside the pure rule evaluator. They produce timestamped observations that become inputs to a run. That separation allows replay without calling a changing registry, while a fresh evaluation can explicitly request a newer source observation.

### 7.2 Evidence intake and extraction

Accept PDF and selected image/video formats after MIME inspection, configured size/page/duration limits and malware checks. Assign random storage IDs; retain original filename only as metadata. Reject or quarantine unsupported encryption, active content, embedded executables, malformed files, decompression bombs and excessive resource use. Parse in isolated workers with no general outbound network, bounded CPU/memory and wall time. Apply platform-appropriate isolation; Linux `rlimit` examples from the earlier report are not a Windows security control.

Use the text layer where reliable; render/OCR scanned regions. Maintain coordinate transforms so a field can be highlighted on the displayed page after rotation or deskew. Store raw text, normalized value, language, model/parser version, confidence and evidence region. Ground optional model extraction in actual page spans; a plausible but ungrounded value becomes unknown. Confidence must be calibrated on the held-out data rather than treated as an arbitrary model score.

Reviewers can correct extraction, not silently modify the uploaded certificate. Store old/new value, reason, actor and timestamp. Corrected facts generate a new fact-set version and new evaluation. Date normalization preserves the raw date and an ambiguity marker; “03/04/2026” cannot be normalized without a format basis.

### 7.3 Core data entities

| Entity | Required fields and invariants |
| --- | --- |
| Institution / Application | Tenant, institution ID, category, cycle, stage, jurisdiction, submitted revision, authorized portal reference |
| InstitutionalRecordVersion | Record type, source system, record key, effective interval, retrieval time, payload hash, synthetic flag; covers EoA, intake, accreditation, faculty, TER and deficiencies |
| EvidenceVersion | Document ID, version, parent version, storage key, SHA-256, media type, uploader, original and received times, access classification; originals immutable |
| ExtractedField / FactSet | Raw and normalized values, units, date basis, page/frame regions, extraction method/version, confidence, correction provenance; canonical fact-set hash |
| Claim / EvidenceLink | Claim subject and period, supporting/contradicting link, evidence version, field/record IDs, relationship and scope |
| VerificationAttempt | Provider, authorized method, request key, source reference, timestamps, status, matched fields, integrity/freshness, response hash, simulated flag, retry lineage |
| RuleSource / RuleLayer | Publisher, URL, file hash, printed/PDF locator, clause, applicability, effective period, interpretation, author/approver and publication state |
| EvaluationRun / Finding | Frozen input references, resolved rules hash, evaluator version, outcomes, findings, evidence references, limitations and calculation trace |
| ResponseWindow / ResponseVersion | Process authority, allowed scope, deadline, request reason, evidence manifest, field diff, round and reassessment lineage |
| ReviewAction | Actor, authority, previous state, new state, observation, evidence links, reason and any second approval |
| Alert / DeliveryAttempt / Task | Trigger, owner, dedup key, due time, status, acknowledgement, escalation and delivery history |
| AuditEvent / AccessEvent | Actor/service, action, object/version, permitted scope, request ID, result, event time, previous-event hash; independent checkpoint reference |

Database constraints must prevent cross-tenant evidence links, reuse of a stale response window, self-approval of rules, updates to published rule content and deletion of audit history by routine application roles. Repeated requests use idempotency keys and expected revision numbers.

### 7.4 Rule representation and resolution

Each rule stores separate fields for source verification, interpretation approval and publication approval. Include rule ID, family, requirement type, document class, programme, level, institution type, jurisdiction, application categories, essential/desirable classification, cycle interval, effective dates, comparison basis, units, rounding policy, source locators and supersession links.

Use numeric cycle years such as `2026`, not arbitrary free-text lexical ordering. Treat academic cycle, legal effective date, submission date, scrutiny date, source-observation time and evaluation time as distinct. A source's publication date is not automatically its legal effective date.

Resolution selects applicable published layers and explicit supersession relations. Conflicting changes to the same rule scope block publication unless resolved by the authorized owner. Avoid the rule “latest document always wins”: scope, legal authority, court directions and specific instructions matter. A proposed exception records its authorized legal basis; a generic admin override cannot activate an unverified threshold for adverse use.

Illustrative rule record, **P**:

```json
{
  "rule_id": "INFRA.INTERNET.301_600",
  "source_id": "U02",
  "source_locator": {"clause": "Annexure 4.1 note 5", "printed_page": 92, "pdf_page": 108},
  "source_content_checked": true,
  "interpretation_state": "PENDING_APPROVAL",
  "publication_state": "DRAFT",
  "academic_cycle_start": 2026,
  "scope": {"intake_min": 301, "intake_max": 600},
  "minimum": {"value": 300, "unit": "Mbps"},
  "input_basis": "approved_intake_per_authorized_interpretation",
  "effect": "POTENTIAL_DEFICIENCY",
  "adverse_action_allowed": false
}
```

The real record must use the actual source SHA-256 from the manifest, not an empty-string hash. Every published run snapshots resolved rules and their provenance. Evidence extraction can be nondeterministic; replay the frozen extracted facts. Reproducibility of the evaluator does not imply that a fresh OCR run reproduces every pixel decision.

### 7.5 Finding contract

Every finding carries an ID, run and requirement, category, scope, observed/expected values and units, rule/source locator, evidence references, source observation if any, computation trace, confidence/unknown reason, benign explanations, proposed reviewer action, applicant-safe explanation, and current review disposition. Store `adverse_action_allowed=false` for machine outputs.

Keep source status and forensic severity outside the finding's regulatory consequence. A report may identify a potential deficiency without alleging manipulation. A reviewer must be able to inspect the precise evidence behind the conclusion and dismiss or escalate it with a reason.

### 7.6 API and portal integration

| API group | Proposed operations | Critical controls |
| --- | --- | --- |
| Intake | Create/import application; upload evidence; submit frozen revision | Tenant authorization, idempotency, portal reference reconciliation |
| Evidence | Fetch authorized page/frame; inspect fields; submit correction | Document-version access check, private caching, access log |
| Evaluation | Start run; read findings and report; compare runs | Immutable inputs; expected revision; simulation labels |
| Verification | Queue attempt; inspect response; record manual confirmation | Provider allowlist, authorized scope, auditable evidence |
| Rectification | Open response window; submit allowed response; compare revisions | Stage policy, scope enforcement, expiry and concurrency checks |
| Rules | Draft layer; simulate impact; approve; publish; supersede | Separate identities, signed release and fail-closed conflicts |
| Review | Record observation; request evidence; escalate; mark ready for authority | Server-side role and stage checks; statutory authority retained |
| Audit | Pending tasks, alert history, access history, replay export | Scoped auditor role, redaction, export logging |

Publish a tested OpenAPI contract and an example AICTE adapter mapping before claiming integration readiness. Proposed SSO accepts a trusted identity assertion and maps role/region/institution on the server; the client cannot choose a privileged role at login. AICTE connectivity, source schemas, authentication, writeback rights, rate limits and sandbox availability are **O** until supplied by the owner. A standalone mock portal demonstration should say “designed for integration”.

### 7.7 Remediation and planning

A remedy states what evidence or inventory would address the particular finding under the loaded rule interpretation. It does not guarantee approval. Start with transparent arithmetic: missing certificate -> required slot and issuer class; bandwidth deficiency -> required tier; printer shortfall -> missing number subject to approved rounding. For example, at approved intake 420 and observed bandwidth 100 Mbps, the base table calls for 300 Mbps. A remedy proposes an evidenced upgrade to at least 300 Mbps. No faculty-cadre ambiguity is needed for this demonstration. [U02, printed 92 / PDF 108]

Evaluate proposed remedies with the same engine. List which checked deficiencies close, which remain, and whether a proposed change is permitted at this stage. Intake reduction is an authorized application change, not a button that removes already admitted students or rewrites historical approved intake. Multi-year cohort stock, programme sharing, new-course stages, division sizes and nonmonotone applicability can defeat the earlier closed-form/binary-search planner. Use constrained scenario enumeration initially; apply monotonic search only to rule families with a tested monotonicity property.

## 8. The seven additions: complete functional specification

### 8.1 Addition 1: minimal, advisory video handling

Add `video_role` values such as EVC_WALKTHROUGH, WEBSITE_DISCLOSURE and SUPPLEMENTARY_EVIDENCE. Store codec, container, duration, frame rate, dimensions, claimed capture location/time and available metadata. Separate claimed capture time from file creation and receipt time. A legal video requirement is evaluated only for the applicable role and category.

Proposed bounded processing: accept a configured maximum file size and duration; sample one frame every 10 seconds, with scene-change candidates and a cap of 180 analyzed frames per video. These are resource policies, not AICTE norms. Preserve timestamps and sampling parameters; do not suggest that sampled frames establish complete scene coverage.

Use hashes and calibrated near-duplicate matching to identify repeated frames or candidate matches with earlier evidence. Provide a contact sheet linking to timestamps. Geotag comparison reports distance from the declared campus only when both coordinates exist and have a known datum. Missing EXIF/GPS is “not available”, not “location false”; GPS can be spoofed. A repeated frame or a long video does not prove current infrastructure availability.

For URL evidence, support an authorized viewer/link capture. Do not scrape protected video platforms or pretend a local-file duration check verifies an inaccessible remote video. Store a permitted snapshot/metadata reference where available.

**Acceptance:** correct duration on known fixtures; no automatic source mismatch from duplicate frames, missing GPS or short duration; deterministic bounded sampling; officer can open flagged timestamps; all views logged. Demonstrate a short website clip and a differently scoped EVC-duration example. The distinction is sourced; analysis thresholds are proposed.

### 8.2 Addition 2: alerts with triggers, owners, timers and deduplication

| Trigger | Proposed recipient and timer | Resolution / deduplication |
| --- | --- | --- |
| Required evidence missing after screening | Applicant in draft; officer after submission; create within 60 seconds of run completion | One open alert per application, requirement, evidence revision and trigger |
| Certificate nearing expiry | Assigned officer; applicant if process permits; 30/7/1-day reminders, configurable | Cancel when replaced or out of scope; distinguish future warning from expired finding |
| Source timeout or service failure | Verification owner; retries after 5, 30 and 120 minutes; manual task after 24 hours | Update one outage task; record attempts, not repeated institution accusations |
| Potential serious inconsistency | Assigned officer; immediate queue event | Acknowledge, dismiss with reason, request evidence or escalate |
| Permitted response deadline | Applicant and assigned officer; 48/24-hour reminders and due-time event | Deadline comes from authorized window; no invented statutory SLA |
| Unauthorized access or permission anomaly | Security owner; immediate operational alert | Keep security alerts separate from application compliance findings |

All timer values above are **P**, not handbook deadlines. Use a transactional outbox so committed findings produce durable alert work. Event ID plus trigger scope forms the dedup key. Replayed jobs must not resend notifications. Record created, queued, sent, failed, retried, delivered-if-confirmed, acknowledged, escalated and resolved states; delivery is not the same as acknowledgement.

Prototype delivery can remain in-app with a simulated email sink. This report authorizes no real messaging to institutions. Production email/SMS requires the intended channel, configured recipients and service authorization.

**Acceptance:** repeated evaluation of unchanged facts creates no duplicate open alert; replacing evidence closes the prior alert with lineage; outage retry creates a manual task at the configured threshold; a delivery failure is visible in the audit trail.

### 8.3 Addition 3: validation reports and scoped rectification

An officer report contains application ID/category/cycle, submission and run versions, rule release/hash, source currency label, completeness counts, six-status breakdown, forensic concerns, compliance findings with evidence and calculation, unavailable checks, proposed tasks, process stage, permitted response scope and reviewer disposition. Footer: preliminary decision support; no approval/rejection conclusion from the system.

An applicant report contains understandable deficiencies, the relevant source/clause, required evidence, what edits are permitted, the authorized due date and how to respond. Exclude another institution's personal information, internal security details and unnecessary detector mechanics. Do not hide evidence or reasons required for a formal notice or a fair response; the competent authority determines disclosure for official action.

Reports are versioned PDF plus structured JSON. Include a verification manifest for authorized internal exports. Rectification generates a new `ResponseVersion`, evidence replacements linked to predecessors, normalized field diffs, changed rule dependencies and a re-evaluation report. Old findings remain queryable; closure is a new disposition/event.

**Acceptance:** v1 cannot be overwritten; changing an unrelated intake field outside the allowed request is blocked; the authorized response produces a v1-v2 comparison; resolved and newly observed findings are distinct; the original submission remains reproducible.

### 8.4 Addition 4: document view and download logging

Log original-document access, page-image access, preview generation, video/frame access, export generation and download. Capture actor/service ID, role and tenant scope, object/version, action, authorization result, server time, request/session reference, purpose/case assignment and bytes served where useful. Minimize IP/device details according to the approved security policy; never log raw certificate contents or tokens.

Prefer an authenticated streaming endpoint for the prototype. A signed storage URL alone records URL issuance, not necessarily a completed download or human reading. If signed URLs are used, correlate storage delivery logs and user/session authorization. Do not advertise “viewed” when all that is known is a browser request. Cache controls must prevent a public CDN from serving private pages.

**Acceptance:** an allowed preview and export have correlated access events; unauthorized access is denied and logged; applicant A cannot obtain applicant B's original, thumbnail or report by changing an ID; an auditor can inspect access by object/version.

### 8.5 Addition 5: audit-history and pending-action screens

The application page must include two working views. **Audit history** filters events by actor, time, evidence version, rule release, verification attempt, alert and action, and opens the supporting object. **Pending actions** shows owner, reason, created/due time, stage, dependency, next permitted action, last attempt and escalation state.

Provide a reviewer inbox for “waiting on applicant”, “waiting on source”, “waiting on interpretation”, “waiting on officer” and “ready for authority”. Keep the application summary counts aligned with these stored tasks. Avoid charts fed by unrelated mock numbers.

**Acceptance:** an upload, screening run, source outage, alert, officer observation, permitted response and reassessment appear in order; each pending task opens the relevant evidence; a resolved task leaves the active list but remains in history.

### 8.6 Addition 6: one visible infrastructure-discrepancy check

Choose a narrow, testable demonstration: **visible computer equipment compared with the declaration for that pictured room**. Use a licensed detector for monitors/equipment only if its supported classes and validation justify the label. A generic “monitor” detection is not automatically a functional computer count. Show boxes, detection confidence, room identity, image coverage and an officer-correctable count.

For a synthetic room declared to contain 20 workstations, an image showing 12 clearly visible monitor candidates produces: “12 candidates visible in the supplied view; declared room count 20; full-room coverage and functional inventory are unconfirmed. Request additional views or inspect.” It does not prove an eight-computer shortage. Multiple views require object association to avoid double counting; lack of reliable association means no merged total.

The declaration, inventory list and photo must refer to the same room and period. Store an evidence-quality flag for occlusion, low light or partial coverage. Human correction of a box/count is audited. Actual required PC inventory still comes from the applicable rule and approved input basis, not the detector.

**Acceptance:** a live run on held-out photos produces overlays and the advisory comparison, with recorded runtime and counting errors. If that cannot be built, explicitly mark computer vision “optional, where feasible”, retain manual image comparison and floor-plan table reconciliation, and never present canned boxes as a working model.

### 8.7 Addition 7: three independent dimensions

Implement Section 6.1 in the data model, API, report and dashboard. This is a non-negotiable correction to the old corroboration table and status precedence. Two forensic signals may prioritize a review task; they do not create a source result. A completeness failure is not an issuer mismatch. A manual confirmation needs the officer, source/method, evidence, scope and timestamp; it is not an unrestricted “mark verified” toggle.

**Acceptance:** automated tests cover all six examples in Section 6.1; changing a forensic concern leaves the source-verification field unchanged; a missing document cannot receive a verification attempt for a nonexistent version; application roll-ups preserve all count dimensions.

## 9. Source-verification feasibility and authentication boundaries

### 9.1 Describe methods, not a misleading single trust ladder

Use method badges: DECLARED, DOCUMENT_CONSISTENCY, SIGNED_BYTES_VALIDATED, AUTHORIZED_SOURCE_MATCH, RECORDED_MANUAL_CONFIRMATION and ON_SITE_OBSERVATION. Add identity binding, claim coverage, time validity, freshness and authorization as separate attributes. Physical inspection and cryptographic evidence answer different questions; neither belongs on a universal scalar ladder.

A signature check evaluates byte integrity, signing certificate chain, signing-time evidence where available, revocation information, permitted changes after signing and signer-to-issuer binding. A valid applicant signature is not the issuing fire authority's confirmation. A QR code is just data until its signature or authorized destination is established. Offline checks with unavailable revocation evidence must disclose that limitation. CCA publishes root material and guidance on chain and revocation checks. [S12]

### 9.2 Integration matrix

| Evidence class | Proposed production path | Access/coverage constraint | Prototype and fallback |
| --- | --- | --- | --- |
| Existing EoA, approved intake, TER, earlier deficiencies | Authorized AICTE record adapter | Owner approval, schemas and freshness required | Synthetic internal records, clearly labelled; reviewer comparison |
| Affidavit 2 | Match portal-generated data; validate applicant signature and formalities | Portal access and signer identity; does not authenticate all annexures | Real parsing/signature capability if built; synthetic applicant record |
| Faculty degree | DigiLocker/NAD-supported issued document with permitted sharing | Requester onboarding, user authorization and actual issuer/document availability | Consent-flow simulator; manual evidence task |
| Institutional entity records | EntityLocker where the institution/document/issuer is supported | Entity authority, partner onboarding and specific coverage | Proposed adapter; no claim that all land/fire documents exist there |
| Fire certificate | State-authorized interface, signed record or recorded officer lookup | Varies by state and authority; no assumed nationwide API | Mock provider plus offline signature checks where available |
| Land/occupancy/building documents | Competent authority record and permitted state/local lookup | Jurisdiction-specific access; Annexure 14 has limited document scope | Synthetic response; manual source confirmation |
| Structural certificate | Engineer identity/registration and certificate evidence, as applicable | A format check does not establish structural safety | Manual confirmation and inspection routing |
| Audited accounts / UDIN | Authorized ICAI workflow and record comparison | Valid identifier syntax is not authentication; do not invent an API | Mock response; recorded manual lookup |
| NBA/NAAC accreditation | Authorized or public body record matched to institution/programme/period | Accreditation scope and historical validity matter | Frozen public test fixture or synthetic record, labelled |
| Infrastructure media | Metadata, near-duplicates, visible evidence and inspection | Cannot establish ownership, current operability or complete inventory alone | Advisory processing and reviewer tasks |

DigiLocker supports requester/issuer exchange and registration. EntityLocker is specifically intended for organizations and publishes requester resources; it is a useful addition to the earlier individual-centric integration story. Neither documentation page proves this team has access, nor that an AICTE certificate category is covered. [S10, S11]

Provider results must include `simulated`, `authorized_access_basis`, `source_record_time`, `queried_at`, `claim_scope`, `response_sha256` and `verification_method`. A mock result may exercise VERIFIED in a test harness, but every user-facing occurrence must say “SIMULATED SOURCE RESULT”; exclude it from live source-success metrics.

## 10. Competition and differentiation strategy

### 10.1 Evidence from competing implementations

This is a bounded public-source review, not a market census or independent execution benchmark. Fixed commits were recorded on 26 October 2026. A missing feature in the inspected files is “not established in this review”, not proof it does not exist elsewhere.

| Implementation | What is evidenced | Implication for positioning |
| --- | --- | --- |
| Pramana, commit 782d4d8127ea848798370238b622e18f19258ed2 | C-S: rule-impact UI and backend comparison; readiness actions with numerical faculty/bandwidth advice; rectification-scope tests; sourced rule YAML. C-R: signature, forensics, evidence pack, privacy and evaluation claims | Impact comparison, readiness advice, scoped rectification and cited rules already have overlap. Differentiate the governed lifecycle and prove the implementation |
| CrashCoders / viraj-1709/aicte, commit 0c1ab2d9faf75ba2261a5802a3e75834d5cfcc8b | C-S: verification pipeline imports and calls a mock issuer service; configurable rule data. C-R: forensics, geo-checks, dossier and feedback behavior | Do not copy performance claims or describe mock registries as live; demonstrate calibrated uncertainty and amendment control |
| SmartValidate, commit 28173fd5d0086842b2d8aad90b447f4e313cb38e | C-S: SimulatedVerificationAdapter with deterministic fixture/keyword responses. C-R: end-to-end application scenarios and audit/dashboard features | Scenario coverage and safe outage behavior are baseline expectations; distinguish real authentication from simulations |
| SIH11, default branch reviewed | C-R and repository layout: frontend folder, four consoles and explicitly simulated role access | UI breadth is not evidence of backend enforcement; show actual permission and workflow controls |
| CipherCore-verify, public repository reviewed | C-R: full-stack, API, blockchain and issuer-verification assertions. Hosted demo was unavailable in this run; backend claims not audited | Do not repeat the old “demo-only” characterization as fact. Live-source and blockchain assertions remain unvalidated here |

Primary project sources: [S08a-S08e]. No competitor tests were executed. Their quoted accuracy or timing values are not comparable to an independently measured benchmark.

Pramana's inspected impact endpoint reevaluates old and active rules against facts built from current application documents. Its UI describes the operation as comparison with the same inputs. This review does not establish a frozen historical-facts replay contract. That is a specific opportunity to prove a stronger contract, not evidence that the competitor always produces wrong results. [S08a]

### 10.2 Adjacent products and existing infrastructure

Microsoft Document Intelligence and Amazon Textract provide document extraction capabilities, including structured content such as forms/tables. They are credible building blocks or procurement alternatives for the extraction layer; their overview documentation does not establish the complete AICTE governance workflow. DigiLocker and EntityLocker are authenticity/document-exchange infrastructure to integrate with. AICTE already produces online deficiency reports. The relevant comparison is the additional review value of this workbench over those components and workflows. [S07, S10, S11, S13, S14]

### 10.3 Differentiators worth demonstrating

| Proposed differentiator | Why it matters | Evidence needed before claiming it |
| --- | --- | --- |
| Approved amendment lifecycle with frozen historical facts | Avoids silent retrospective rule changes and uncontrolled admin edits | Candidate-layer diff, distinct approvers, immutable release, replay of earlier run |
| Process-aware remediation | Prevents helpful advice becoming unauthorized post-submission edits | Authorized response policy, scope rejection, version diff and closure trace |
| Source/forensic/completeness independence | Reduces misleading authentication claims and unjustified review escalation | Data/API contract and benign/outage/forensic test cases |
| Executable evaluation replay | Gives a reviewer reproducible logic, beyond a signed report | Offline verification of hashes and deterministic findings; tampered bundle fails |
| Disclosure reconciliation with provenance | Compares application, authorized history and public disclosure by period | Dated page snapshot or permitted evidence capture; mismatch explanation and stale-page fallback |
| Evaluation that measures errors and burden | Makes accuracy and workload claims assessable | Frozen held-out benchmark, confidence intervals, coverage, review burden and timed study |

Do not call this a novel AI algorithm or patentable invention. The defensible innovation is an integrated system design and a better evidenced workflow. “Not established in the inspected competitors” is the strongest absence statement supported by this review.

### 10.4 Revise the old U-01 to U-12 priorities

Retain U-01 layered rules, but add explicit legal applicability and historical fact snapshots. Retain U-02 with the narrower novelty claim: governed publication plus replay, because impact comparison exists elsewhere. Retain U-03/04 as constrained remedies and planning with closure checks, acknowledging existing numerical advice. Fold U-05 claim coverage and U-06 feasibility into the main review screen. Keep U-07 disclosure audit as a second-phase differentiator. Retain U-08 executable replay. Keep U-09 to plan-area table reconciliation before free-form geometric CV. Defer U-10 inter-officer agreement dashboards and U-11 calibration automation. Make U-12 evaluation transparency a core deliverable, but do not label an unmeasured safety panel “proof of safety”.

## 11. Prioritized build plan

### 11.1 Assumptions and release scope

Planning assumption **P**: a team with approximately six contributors, 12-15 working days, a local demonstration and no government credentials. This is an effort estimate, not a known SIH schedule. If the actual idea-submission deadline is confirmed as 28 October, use 26-28 October for the pitch/specification and a thin walkthrough; do not promise the full platform by that date. Finale dates and official slide constraints remain unverified.

Start with ordinary EoA and one scoped change category for a limited programme set. Demonstrate an Engineering case with clear document, bandwidth and expiry rules. Include a rule-ambiguity example as an intentional manual-review outcome. Show other programmes as supported by the schema but unimplemented until their rule packs pass the same gates.

### 11.2 Backlog with dependencies and exit criteria

| Priority / window | Work package | Depends on | Done when |
| --- | --- | --- | --- |
| P0 / days 1-2 | Source register, verified baseline subset, ambiguity catalogue, status contract, synthetic fixtures | Source analysis | Every active demonstration rule has a locator; unresolved cadre rules abstain |
| P0 / days 1-3 | Authentication, tenant/object permissions, encrypted storage, upload isolation, event logging | Core schema | Cross-tenant previews/exports denied; originals and access events versioned |
| P0 / days 2-4 | Extraction with evidence regions and corrections; historical record adapter | Safe storage | Digital/scanned branches work on fixtures; unknown fields remain unknown |
| P0 / days 3-5 | Pure evaluator; category checklist; distinct dimensions; source adapters and outage path | Facts and rule subset | Six source outcomes mapped; missing evidence and forensic flags cannot create source mismatch |
| P0 / days 4-6 | Officer workspace, officer/applicant reports, pending actions and audit history | Runs/events | Reviewer can trace each finding and open its task/evidence |
| P0 / days 5-7 | Scoped response loop, version diff, alert outbox/dedup, document-access history | Workflow policy | Permitted response closes a finding; unauthorized edits and duplicate alerts blocked |
| P1 / days 6-8 | Candidate rule simulation, distinct approvers, publication, old-run replay | Frozen facts/rules | Historical run unchanged after publication; approval and release evidence visible |
| P1 / days 7-9 | Video basics, photo near-duplicates, floor-plan table reconciliation, visible equipment check | Evidence pipeline | All seven additions have working evidence or an explicit optional-CV limitation |
| P1 / days 8-10 | Transparent remedy and two constrained planning scenarios | Approved arithmetic | Re-evaluation shows the remedy's specific effect; no promise of approval |
| P1 / days 9-12 | Benchmark, failure injection, access/retention tests, replay package, offline rehearsal | End-to-end flow | Metrics report separates targets/results; clean startup and replay documented |
| P2 / days 12-15 | Disclosure audit, extra languages/programmes, improved calibration and accessibility | Stable MVP | Added capability passes held-out and permission checks |

Assign clear ownership: one contributor owns regulatory content and source review; one owns evaluator/governance; one owns evidence/OCR; one owns workflow/integration; one owns UI/reporting; one owns evaluation/security and reproducibility. This is a team-role proposal, not a request to spawn agents.

### 11.3 If build time is compressed

For a concentrated 36-hour prototype, retain one category, a small cited rule subset, two document classes, three dimensions, a mock-source outage case, reports, scoped response, access logging, pending tasks and a single amendment replay. Demonstrate basic video metadata and manual media review. Mark CV optional if a working count model cannot be verified. Ship an honest narrow vertical slice rather than a menu of nonfunctional modules.

Cut in this order: inter-officer analytics; automatic calibration; graph visualization; broad multilingual claims; arbitrary floor-plan geometry; live website crawling; unrestricted intake optimization; expansive forensic detectors; extra categories. Never cut permission enforcement, source labels, original evidence retention, human authority, alert history or the separation of verification from forensic concern.

### 11.4 Demonstration release gate

The release must support an authenticated journey from evidence upload to findings, report, permitted response, reassessment and audit history. Every public capability must have a reproducible example. No source simulator can be labelled live; no UI-only role gate can be described as security; no prepared metric can be described as measured. Freeze the demo dataset and release ID, rehearse on a clean machine with required assets already provisioned, and retain a backup recording clearly identified as such.

## 12. Demo narrative and judging strategy

### 12.1 Five-minute primary story

| Time | On-screen action | What it proves |
| --- | --- | --- |
| 0:00-0:25 | Open a synthetic EoA case with current rule release, source badges and three separate status groups | Scope, transparency and decision-support role |
| 0:25-1:05 | Open a missing document, an expired certificate and a mock-source outage; show different outcomes | Correct semantics and safe failure |
| 1:05-1:40 | Open a bandwidth finding; click the source locator and evidence; view a neutral remedy | Applicable rule, calculation and actionable correction |
| 1:40-2:25 | Officer opens a permitted response; applicant submits updated bandwidth evidence; show the diff and reassessment | Scoped rectification and preserved history |
| 2:25-3:15 | Compare a candidate amendment against frozen facts; self-approval fails; second identity approves; old run replays | Governance beyond a simple impact screen |
| 3:15-3:50 | Show equipment candidates on a photo and a video contact sheet; no source mismatch is created | Honest infrastructure assistance |
| 3:50-4:25 | Open pending-source task, alert history and document access log | Real operational accountability |
| 4:25-5:00 | Show benchmark card with n/CI/coverage; verify exported replay manifest; show an unresolved-rule example | Measured limits and reproducibility |

For the amendment scene, use either a source-backed historical comparison or a conspicuously labelled hypothetical change. A clean example is international E&T PG seat capacity changing from 15% in the base text to 25% in the mirrored amendment, with approved base intake 60 and a hypothetical request for 12 seats: 9 versus 15 capacity. State that other conditions are held fixed and not approved by the capacity calculation. Do not use the old PoP “11/60 passes all rules” example, which ignores the reservation and qualification conditions. [U02; S06]

Keep the original packet untouched. A what-if view has a distinct banner and cannot issue a notice. If the ruleset is not accepted for production, say this is a governance demonstration using reviewed mirror text.

### 12.2 Suggested deck narrative

Use the actual organizer template when available. The proposed content order is: (1) reviewer problem and current portal baseline; (2) full application/evidence workflow; (3) data and architecture boundaries; (4) amendment governance and scoped rectification; (5) seven additions and trust model; (6) competitor overlap and specific demonstrable advantage; (7) measured evaluation or clearly labelled evaluation plan; (8) integration dependencies, security and build feasibility. Do not claim official judging weights or rubrics that were not supplied.

### 12.3 Questions the team should answer precisely

“What is unique?” -> The demonstrated combination and contracts, especially approved amendments with historical replay and permitted correction; impact and OCR alone are not unique.

“What is real?” -> Name exactly which checks execute locally, which source results are simulated, and which external integrations require authorization. Show this in the UI, not just in a footnote.

“Where is AI?” -> Document classification/extraction, calibrated matching and optional visual counting. Rules and statutory authority remain explicit; an LLM does not invent norms.

“Can it detect a convincing forged document?” -> Not reliably without an issuer anchor. Internal consistency and a neat layout do not establish authenticity. Route uncertainty to an authorized verification task.

“Does a photo count prove noncompliance?” -> No. It identifies visible candidates and an evidence gap. Inventory and inspection remain necessary for stronger conclusions.

“Why is the cadre rule not automatic?” -> The supplied table's printed components do not reconcile; the system exposes the ambiguity and requires an approved interpretation instead of inventing one.

## 13. Evaluation plan: targets, denominators and failure cases

### 13.1 Dataset and ground truth

Proposed staged evaluation: 60 development packets for debugging; a frozen test set of 200 independent application packets, including at least 100 clean/benign packets; and a later 300-clean-packet safety expansion if needed. These are planned sample sizes, not existing data. Use different institution identities, document templates, layouts, issuer styles and generator families across train/dev/test; changing only a random seed is insufficient to establish template generalization.

Keep all versions of a packet, its near-duplicate photos, forged twins and same-institution documents in the same split. Include digital and scanned pages, skew/recompression, missing metadata, legitimate signatures/updates, language-specific cases, date boundaries, same-campus shared facilities, stale history, unknown state authorities and source outages. Regional-language support is claimed only for the languages actually labelled and tested.

Generate ground truth before running the product. Have two independent annotators label important fields, expected rule outcomes, claim matches and discrepancy regions; adjudicate disagreements with a documented rule interpretation. A regulatory reviewer should approve rule ground truth before claiming real-world compliance accuracy. Public signed government PDFs can test cryptographic processing; they are not a representative AICTE-certificate dataset.

### 13.2 Eight required metric categories

| Metric | Definition and denominator | Proposed acceptance target, not result |
| --- | --- | --- |
| 1. Extraction accuracy | Normalized exact matches / all ground-truth required fields; missing predictions count as errors. Also report per-field and per-language results and accepted-field coverage | At least 95% digital and 90% scanned critical-field accuracy on defined test strata; measure, do not promise |
| 2. Validation accuracy | Agreement with adjudicated outcomes per applicable requirement, plus whole-packet exact match; report NOT_EVALUABLE separately | At least 95% requirement agreement; all ambiguity fixtures abstain correctly |
| 3. Anomaly performance | Precision, recall and F1 at document and packet level; forensic flags separate from source mismatch; clean false-flag and false-adverse-indicator rates | At least 90% precision and 85% recall for supported planted anomaly families; no unsupported fraud claim |
| 4. Successful source verification | Authoritatively resolved eligible claims / all eligible claims requiring source verification, including unavailable outcomes in the denominator; also report request and source coverage | Live result unavailable until access exists. Mock adapter status-mapping tests reported separately |
| 5. Discrepancy reliability | Correctly matched/localized seeded discrepancies / all seeded supported discrepancies; page/frame/claim identity plus region overlap where appropriate | At least 90% supported discrepancy recall; 100% findings have resolvable evidence references |
| 6. Verification time | End-to-end elapsed and active processing time per packet; stage breakdown, cold/warm, median/p95, pages and hardware | Proposed p95 under 120 seconds for a declared 10-page local fixture profile; external waits/video excluded only in clearly separate timing |
| 7. Alert timeliness | Trigger-committed to alert-created/visible/delivered timestamps, separately; correctness and duplicates included | In-app p95 under 60 seconds; zero duplicates under replayed identical event tests |
| 8. Manual effort reduction | Paired active reviewer time at comparable correctness, including corrections and rework | Hypothesis: at least 30% median reduction in the study; no achieved saving before measurement |

Confidence scores are not accuracy. Status-mapping accuracy is not source-verification success. A simulator returning a correct timeout outcome has passed a robustness test but has not verified a real certificate. Report all three separately: coverage, authoritative resolution, and adapter correctness.

### 13.3 Error and uncertainty reporting

Define **false adverse indicator rate** as clean packets wrongly receiving an actionable mismatch/expiry/potential-deficiency indicator divided by all clean packets. Actual statutory adverse action should remain impossible for the system actor. Separately report forensic false-flag rate, clean-packet manual-review burden, abstention rate, automatic assessment coverage, and error among automatically assessed items. Avoid the ambiguous acronym FAR, which often means false acceptance in authentication contexts.

Use packet-level cluster bootstrap intervals for correlated fields/requirements and paired reviewer timings. Wilson intervals are suitable for independent packet-level binomial outcomes; do not pretend hundreds of fields in one packet are independent samples. With zero events in 100 independent clean packets, the approximate one-sided 95% rule-of-three bound is 3%; with 300 it is about 1%. Zero observed errors is not evidence of zero risk.

Every results card includes target, measured value, numerator/denominator, sample definition, 95% interval, dataset version, release commit, hardware and exclusions. No target is prefilled into a measured column. For precision/recall/F1, report counts and packet-bootstrap intervals or an explicitly stated method.

### 13.4 Source fault-injection suite

For each implemented adapter test exact match, field mismatch, expired record, record not found, timeout, service failure, rate limit, malformed payload, stale cached record, authentication failure, untrusted TLS and ambiguous identity. “Not found” is not automatically a fake document; identity ambiguity and incomplete registry coverage require manual confirmation. Keep raw provider events immutable and record every mapping decision and retry.

The suite must prove that repeated failures do not create repeated alerts, open access, auto-approval or adverse decisions. Cached results show age and may be unsuitable for current verification even if a historic response was successful.

### 13.5 Adversarial and benign-case matrix

| Scenario | Expected safe outcome | Remaining limitation |
| --- | --- | --- |
| Text expiry changed in an incremental PDF revision | Forensic concern and source comparison if available | Entirely regenerated/flattened documents may leave no revision history |
| Recompression, mobile scan, absent EXIF | No forgery conclusion from those facts alone | Evidence quality may still be insufficient |
| Self-consistent newly generated QR | Not issuer-authenticated without signature/authorized destination | A convincing forgery may be undetectable locally |
| Signed PDF modified outside/inside permitted scope | Explicit signed-range/change-policy result and reviewer task | Revocation/signing-time evidence may be unavailable |
| Cropped or recoloured reused lab photograph | Candidate match with side-by-side evidence; forensic concern | Similar rooms and permitted shared facilities can look alike |
| 12 visible equipment candidates, declared 20 | Advisory evidence-gap comparison | Partial view and functional inventory unresolved |
| Missing required document | Completeness finding with no source result | Applicability may itself need clarification |
| Wrong-tenant evidence ID in URL/export | Denied and logged | Requires testing every derived artifact route |
| OCR instruction saying “ignore the rules” | Treated as document data; no tool or policy action | Novel extraction attacks require continued testing |
| Rule source or faculty arithmetic ambiguous | NOT_EVALUABLE and interpretation task | Requires authorized clarification |
| Old run replay after new evidence/rule release | Identical frozen-facts result | A fresh extraction is a different run |
| Alert replay, simultaneous responses, stale window | Idempotent operation or explicit revision conflict | Distributed workers require durable coordination |

### 13.6 Manual effort study

Proposed pilot: eight reviewers, six matched case pairs each, counterbalanced assisted/manual order and different but equivalent cases to reduce memory effects. Use a checklist/PDF-viewer baseline and the workbench-assisted condition. Time active review, correction, evidence requests and final recorded disposition. Record correctness and uncertainty handling alongside time. Aggregate within reviewer; report paired differences and intervals, not 48 independent observations from eight people. If participants are students rather than AICTE officers, label that limitation and avoid national workload extrapolations.

### 13.7 Ablations and engineering checks

Compare rules-only; rules plus historical/cross-document reconciliation; added forensic processing; and added authoritative source evidence. Report accuracy, false indicators, coverage, review burden, latency and cost per packet. This tests whether expensive CV/forensics improve outcomes.

Required engineering checks include tenant separation, role forgery, unauthorized downloads, response-scope bypass, self-approval, stale version races, malicious uploads, parser timeouts, rule conflicts, source failures, date anniversaries/leap-day policy, missing denominators, alert replay, retention holds, restore from backup and replay-bundle tampering. These are proposed acceptance checks, not checks run in this research task.

## 14. Security, privacy and compliance plan

### 14.1 Implemented control evidence required before pilot

Use server-side roles and object-level authorization on every original and derived artifact. Separate rules administration from application decisions. Apply encryption in transit and at rest, with per-object keys or an equivalent managed design and auditable key access. Use isolated workers, restricted network egress, safe viewers, rate limits, upload scanning, secrets management and tested backup restoration.

A hash chain is tamper-evident only within its trust model. An administrator with all signing keys, logs and checkpoints can rewrite them. Use append-only permissions, independently controlled checkpoints and protected/WORM storage where appropriate. Do not call a hash chain a consortium blockchain or an immutable legal guarantee.

### 14.2 Personal data and identity

Prefer authorized AICTE faculty identifiers. If a permitted identifier is needed for duplicate detection, use a purpose-bound HMAC with separately managed keys; this is pseudonymization, not anonymization. Do not claim “zero raw ID storage” if original uploaded documents still contain PAN or other identifiers. Minimize displays, logs, exports, temporary renders and search indexes as well as database fields.

Do not introduce Aadhaar collection, authentication or storage based on a news article. This report does not verify a team entitlement to those services. Any authorized production path should consume only the permitted result/reference from the approved service under its governing conditions. Synthetic identities are sufficient for the prototype.

Keep institute-level records separate from faculty/student personal data. Public disclosure availability does not grant unrestricted reuse or perpetual retention. A disclosure auditor should minimize captured personal fields and retain evidence under an approved purpose and access policy.

### 14.3 Current DPDP position

The official MeitY Gazette for DPDP Rules 2025 has phased commencement: rules 1, 2 and 17-21 on publication; rule 4 after one year; rules 3, 5-16, 22 and 23 after eighteen months. As of 26 October 2026, do not describe all final-rule duties as already commenced. The official index also lists a December 2025 corrigendum; a deployment review must include that and the Act's commencement notifications. Build the privacy controls now, but label this as readiness until the applicable obligations, data roles and legal basis are approved. [S15]

Create a processing inventory: personal-data categories, purpose, legal basis, source, permitted recipients, processor/vendor, retention and individual-rights handling. Distinguish a product consent ledger from a registered Consent Manager under the Rules. Government processing is not automatically exempt, and consent is not automatically the only lawful basis. Obtain the deploying authority's decision on its role and basis.

### 14.4 Retention and incident response

Prototype policy **P**: use synthetic data; transient extracted media expire after a short configured period unless needed for a demonstration; retain benchmark fixtures and release manifests intentionally. Production evidence retention follows AICTE records, appeal, legal-hold and statutory requirements. It is not a blanket “delete after 30 days” rule. Deletion covers originals, thumbnails, frames, OCR caches, indexes, exports, temporary workers and backups according to a documented schedule; retain a minimal authorized tombstone.

CERT-In directions specify a rolling 180-day ICT log requirement within Indian jurisdiction for covered entities and a six-hour reporting rule for specified incidents; applicability and incident criteria require an operational owner. These security logs are a different retention class from application evidence. Build synchronized timestamps, an incident contact, escalation, evidence preservation and a rehearsed reporting process. [S16]

### 14.5 Disclosure audit and external network safety

Restrict fetches to confirmed institution domains and permitted public resources. Block private/link-local addresses, cloud metadata endpoints and unsafe redirects; revalidate destination IPs to prevent SSRF/DNS rebinding. Rate-limit, respect access restrictions, and record retrieval time/content hash. JavaScript-only pages, failed requests and inaccessible PDFs are “not assessed”, not proof a mandatory disclosure is absent. Separate a website's stale publication from an applicant's current claim.

### 14.6 Licensing, accessibility and deployment

Maintain an SBOM covering packages, OCR language packs, detector weights, fonts and sample media. The earlier blanket claim that a particular license disqualifies government deployment is too strong. Choose dependencies with understood obligations and obtain review for distribution/network-use implications; package and weight licenses may differ. Do not assume that an ONNX export changes the original model's license. No production dependency-license audit was completed by this report.

Use keyboard-accessible navigation, readable contrast, text labels alongside status colours, screen-reader names, and accessible structured reports. Test the actual languages supported. Deployment sizing, budget, India hosting choice, availability targets, penetration testing, NIC/SSO compatibility and any procurement certification remain proposed or dependent on the deploying authority; no certification is claimed.

## 15. Claims register and readiness evidence

| Claim | Status now | Allowed presentation | Evidence required to upgrade |
| --- | --- | --- | --- |
| Uploaded handbook has the cited tables and provisions | V-U | “Checked in the supplied APH, with printed/PDF pages” | Accepted current source set before operational use |
| Selected annual amendment wording | V-M | “Checked in an AICTE-issued document copy on a public mirror” | Publisher/authorized-owner confirmation and currency review |
| Pramana has impact comparison and numerical advice | C-S | “Observed in named files at commit 782d4d8...” | Runtime audit if claiming measured behavior |
| Our governed amendment workflow is implemented | P | “Proposed MVP capability” | Demo, tests, separate approvers and release record |
| All seven additions are built | P | “Specified with acceptance criteria” | Working build and recorded test evidence |
| Live AICTE/DigiLocker/state issuer integration | O | “Adapter contract proposed; prototype sources simulated” | Onboarding, permission and a real supported record test |
| Document is authentic | O unless scoped source proof | “This signed range/source record was checked by this method at this time” | Identity binding, authorization, claim coverage and validity evidence |
| Our accuracy/time saving exceeds competitors | O | No superiority percentage claimed | Comparable held-out benchmark and timed study |
| No false accusations | O | “No errors observed in n cases”, only after testing, with interval | Larger independent clean sample and uncertainty reporting |
| First/only solution or novel algorithm | O | “Differentiation proposed against inspected public implementations” | Broader independent prior-art/market review |
| Tamper-proof or immutable | O | “Tamper-evident under this checkpoint/key model”, after implementation | Threat-model validation; avoid absolute guarantee |
| Fully AICTE/DPDP compliant | O | “Designed for reviewed requirements; compliance work remains” | Authorized rule review, legal applicability, implementation audit |

### 15.1 What is complete in this research task

The three uploaded inputs were recovered and examined; the previous claims and recommendations were revised; selected amendment text and public competitor implementations were checked with sources; all seven additions have concrete behavior and acceptance criteria; and the proposed specification, build priorities, demonstration, evaluation and compliance plan are documented.

### 15.2 Dependencies before a real pilot

The regulatory owner must settle current-source completeness, cadre arithmetic/counting/rounding, relaxation scope, BBA/BMS/BCA applicability and conflicting special provisions. The portal owner must provide integration authority and schemas. Each issuer must confirm permitted interfaces and document coverage. The team must implement the narrow slice, run the benchmark, obtain reviewer feedback, and complete privacy/security/retention review. These are real dependencies, not grounds to claim a completed production platform.

## Appendix A. Disposition of the previous 32 corrections

| Old ID | Revised disposition |
| --- | --- |
| C-01 | Replace universal adjunct-removal claim with scoped deletion and PoP amendment; reservation interpretation remains open |
| C-02 | Reject “minus one is verified” assertion; preserve the visible table inconsistency and require approved interpretation |
| C-03 | Use the actual programme/regulator/institution scope; do not import an older standalone architecture ratio as current AICTE law |
| C-04 | UG/PG ratio rows now transcribed from the supplied table; Diploma component arithmetic remains unresolved |
| C-05 | Relaxation text verified; scope, rounding and reliable three-year history still required |
| C-06 | Correct page mapping: Annexure 18 starts printed 180/PDF196; Annexure 14 printed163/PDF179 |
| C-07 | Affidavit formalities verified for the scoped EoA list; match declarations to actual packet evidence |
| C-08 | Thirty-year completion-certificate basis, registered engineer and five-year validity verified; distinguish government documentary alternative |
| C-09 | Mandatory completeness dimension retained; absent document has no verification result |
| C-10 | Extend layered rules with authority, effective period, publication approval and frozen-run replay |
| C-11 | Computing ratios, departmental minimum, printer/plotter and bandwidth provisions checked in Annexure 4 |
| C-12 | Correct category error: Annexure 14 is not a fire-authority list |
| C-13 | Retain server-side roles and tenant/object authorization; no defect in current team code asserted without repository |
| C-14 | HMAC is pseudonymization; originals may still contain IDs; no “zero raw ID” assertion without full pipeline review |
| C-15 | Retain encrypted originals and derived media; log authenticated delivery and restrict caches |
| C-16 | Add records/appeal/legal-hold retention; no blanket deletion policy |
| C-17 | Retain independent audit anchoring and explicit threat model; no immutability guarantee |
| C-18 | Retain hostile-input and injection controls with platform-appropriate isolation |
| C-19 | Review actual license obligations; remove categorical “AGPL cannot be used” implication |
| C-20 | Pin and verify an actual build; no library list presented as installed production stack |
| C-21 | Retain calendar arithmetic; publish anniversary, leap-day and date-basis interpretation |
| C-22 | Replace automatic forensic-to-mismatch table with independent concern and source status |
| C-23 | ELA optional and evaluated as supporting evidence; no fraud conclusion from heatmap |
| C-24 | Font/position anomalies remain advisory and template/language-sensitive |
| C-25 | Photo reuse is a candidate concern, including cross-trust reuse; no automatic issuer mismatch |
| C-26 | Extend audit to inputs, response snapshots, alerts, accesses, rule publication and reviewer actions |
| C-27 | Keep versioned institutional history and actual source-period/freshness |
| C-28 | Keep eight categories; separate real source resolution, coverage and simulated status mapping |
| C-29 | Human gate retained; map competent authority rather than assuming every scrutiny officer can issue every notice |
| C-30 | Authorized faculty IDs preferred; Aadhaar entitlement not established by this research |
| C-31 | Replace misleading single precedence/“Verified institution” roll-up with orthogonal counts and review readiness |
| C-32 | Alerts, audit screens and video basics are core here; optional-CV label remains acceptable only if clearly disclosed |

## Appendix B. Sources and inspected implementation references

All web references were checked or attempted on **26 October 2026**. “Retrieved” does not mean an inaccessible official source was independently authenticated. The accompanying source manifest records local file SHA-256 values and the competitor commits. Locators in this report refer to the exact local copies.

**U01. Uploaded competitive research.** `sources/competitive-research.pdf`, 36 pages, original title “AICTE PS26261 - Corrected Specification v2.1, Competitive Research & Uniqueness Playbook”. Prior analysis, not regulatory authority.

**U02. Uploaded AICTE Approval Process Handbook.** `sources/aicte-aph-2024-27-uploaded.pdf`, 231 pages. Official publisher reference: [AICTE APH PDF](https://www.aicte.gov.in/sites/default/files/APH%20Final.pdf). The uploaded bytes, not an assumed equivalent download, are the basis of V-U locators. [Government launch announcement](https://www.pib.gov.in/Pressreleaseshare.aspx?PRID=1983013&lang=2&reg=48) corroborates the three-year handbook context.

**U03. Uploaded seven-additions image.** `sources/seven-additions.jpeg`. User-supplied scope, not an AICTE circular.

**S01. AICTE access check.** [AICTE home](https://www.aicte.gov.in/) returned maintenance; [approval bureau](https://www.aicte.gov.in/bureaus/approval) and approval-cycle routes were inaccessible in this run. Used only to qualify currency.

**S02. Official SIH route attempted.** [SIH 2026 problem statements](https://www.sih.gov.in/sih2026PS), timeout/access error. Deadline and official current brief could not be confirmed there.

**S03. Accessible brief mirror.** [SIH26261 brief](https://zaidsayyed.in/tools/sih-problem-statements/sih26261). Secondary distribution of problem text; source for the working deliverable/status/evaluation decomposition. Do not call it the official publisher.

**S04. AICTE addendum announcement.** [AICTE public announcement of 2025-26 addendum](https://www.linkedin.com/posts/aicteindia_addendumcorrigendum-2025-26-for-the-approval-activity-7267763906738032641-d-Nr), with [Media AICTE video](https://www.youtube.com/watch?v=PnoMeBMz58s). Confirms release context; not a substitute for clause text.

**S05. 2025-26 addendum text mirror.** [Combined handbook and addendum](https://edu-ecosys.com/AICTE-APH-26-27.pdf), downloaded as `sources/addendum-2025-26-mirrored.pdf`, 261 pages. The URL filename is misleading; PDF pp.234-260 contain the identified 2025-26 cover/messages and amendment text. Key PoP provisions: printed20-23/PDF257-260. Mirror provenance, not issuer-download authentication.

**S06. 2026-27 addendum text mirror.** [AICTE-issued document copy](https://avantiscdnprodstorage.blob.core.windows.net/legalupdatedocs/52940/AICTE-issued-the-Corrigendum-regarding-the-Approval-Process-2026-27-February202026.pdf), downloaded as `sources/addendum-2026-27-mirrored.pdf`, 21 pages. [Hosting context](https://teamleaseregtech.com/updates/article/52940/aicte-issued-the-corrigendum-regarding-the-approval-process-2026-27/) describes a 2 December 2025 issuance; the February filename is not treated as the legal issue date. Supersession/currency requires confirmation.

**S07. Existing portal-generated deficiency report.** [Chandigarh College report](https://www.ccet.ac.in/pdf/auditreports/AICTE/Deficiency%20Report%202025-26.PDF). AICTE-generated document on institution host; evidence of report workflow and submitted-application declaration, not a general legal analysis of all editing rights.

**S08a. Pramana primary project sources.** [Repository](https://github.com/Anexus5919/pramana); fixed commit `782d4d8127ea848798370238b622e18f19258ed2`. Inspected [impact UI](https://github.com/Anexus5919/pramana/blob/782d4d8127ea848798370238b622e18f19258ed2/frontend/src/pages/rules/Impact.tsx), [admin/impact endpoint](https://github.com/Anexus5919/pramana/blob/782d4d8127ea848798370238b622e18f19258ed2/backend/pramana/api/admin.py), [readiness advice](https://github.com/Anexus5919/pramana/blob/782d4d8127ea848798370238b622e18f19258ed2/backend/pramana/insights/readiness.py), [rectification tests](https://github.com/Anexus5919/pramana/blob/782d4d8127ea848798370238b622e18f19258ed2/backend/tests/test_rectification_scope.py), README and rule YAML. Source inspection only.

**S08b. CrashCoders primary project sources.** [Repository](https://github.com/viraj-1709/aicte), commit `0c1ab2d9faf75ba2261a5802a3e75834d5cfcc8b`; [issuer pipeline](https://github.com/viraj-1709/aicte/blob/0c1ab2d9faf75ba2261a5802a3e75834d5cfcc8b/backend/app/pipeline/step5_verify.py), README and rule configuration inspected.

**S08c. SmartValidate primary project sources.** [Repository](https://github.com/sathvik210508/AI-Powered-Application-Validation-Document-Authentication-Regulatory-Compliance-Platform), commit `28173fd5d0086842b2d8aad90b447f4e313cb38e`; [simulated verifier](https://github.com/sathvik210508/AI-Powered-Application-Validation-Document-Authentication-Regulatory-Compliance-Platform/blob/28173fd5d0086842b2d8aad90b447f4e313cb38e/backend/services/verifier.py) and README inspected.

**S08d. SIH11.** [Repository/README](https://github.com/sohamramshette/SIH11). Public frontend layout and explicit role simulation; no runtime test.

**S08e. CipherCore.** [Repository/README](https://github.com/nonutsayan/CipherCore-verify). Repository accessible; [hosted demo](https://nonutsayan.github.io/CipherCore-verify/) inaccessible during this run. Live API/blockchain performance not validated.

**S10. DigiLocker official integration context.** [Data exchange](https://www.digilocker.gov.in/web/data-exchange), [security architecture](https://www.digilocker.gov.in/web/security-architecture), [partner registration](https://api.apisetu.gov.in/). Supports the integration pathway, not project entitlement or document coverage.

**S11. EntityLocker official context.** [EntityLocker](https://entity.digilocker.gov.in/), [resources](https://entity.digilocker.gov.in/web/resources). Organization-focused document exchange and requester resources; specific AICTE coverage unconfirmed.

**S12. CCA primary documentation.** [Root certificates](https://cca.gov.in/root_certificate.html) and [verification guidance](https://cca.gov.in/sites/files/pdf/guidelines/CCA-ESAIG.pdf). These support chain/revocation/identity-validation design; a documentation link is not itself a tested trust store.

**S13. Microsoft primary documentation.** [Document Intelligence overview](https://learn.microsoft.com/en-us/azure/ai-services/document-intelligence/overview?view=doc-intel-4.0.0). Adjacent extraction capability only; no cost/performance comparison was run.

**S14. AWS primary documentation.** [What is Textract?](https://docs.aws.amazon.com/textract/latest/dg/what-is.html). Adjacent text/forms/tables extraction capability only.

**S15. MeitY primary privacy sources.** [DPDP Rules official index, including corrigendum and enforcement timeline](https://www.meity.gov.in/documents/act-and-policies/digital-personal-data-protection-rules-2025-gDOxUjMtQWa?pageTitle=Digital-Personal-Data-Protection-Rules-2025), [Gazette Rules PDF](https://www.meity.gov.in/static/uploads/2025/11/53450e6e5dc0bfa85ebd78686cadad39.pdf), rule1 at English PDF p.24. Phased commencement verified; no full deployment legal opinion is claimed.

**S16. CERT-In primary directions.** [28 April 2022 directions](https://www.cert-in.org.in/PDF/CERT-In_Directions_70B_28.04.2022.pdf), [official FAQ](https://www.cert-in.org.in/PDF/FAQs_on_CyberSecurityDirections_May2022.pdf). Operational applicability and reporting criteria must be mapped to the deploying entity.

