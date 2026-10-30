# NiyamFlow revised solution and complete change register

**Problem statement:** SIH26262  
**Prepared:** 30 October 2026  
**Status:** Proposed solution specification. These changes are not a claim that the new approval workflow modules have been implemented.  
**Purpose:** One standalone Markdown document combining the revised PDF solution, all material corrections to the earlier proposal, delivery priorities and exact research references.

> Use this document as the current proposed design when updating the PPT and prototype. It supersedes conflicting illustrative rules, performance targets and implementation claims in earlier drafts. No application code changes are included in this deliverable.

## Complete change register

The following changes combine the useful requirements identified in the supplied review with the policy, ethical and engineering corrections needed to make them defensible. The review is treated as material to assess, not as an authority that establishes regulatory rules.

| Area | Earlier proposal or suggested patch | Revised solution |
| --- | --- | --- |
| Scope | Generic workflow descriptions left some required views implicit. | Make route families, summaries, role views, undertaking tracking, renewal tracking, EVC milestones, escalation and six report families explicit. |
| Completeness claims | An asserted 88% completion score and 100% bulletproof patches. | Remove unsupported scores. Assess coverage through traceability and executable acceptance evidence. |
| Route coverage | Three illustrative routes, followed by a suggested four-route restriction. | Support the four named families and other authorized combinations; do not hard-code a closed universal list. |
| Route selection | Suggested category-to-route mappings were presented as prescribed. | Use a source-linked, approved decision table; unresolved categories require review. No blanket rule that ordinary EoA always requires scrutiny. |
| Hearing and appeal | SAC and SHC were merged into one interchangeable stage. | Represent distinct authorized triggers, responsibilities, stages and review paths. |
| Case summaries and communications | Mentioned without a clear delivery contract. | Provide a deterministic dossier and governed templates. Separate draft, approval, issue and delivery; a read action must not issue a notice. |
| Dashboards | One work queue with filters. | Define institution, assigned committee, regional, bureau and competent-authority views with server-side scope. |
| Reports | Generic reporting without explicit domain coverage. | Provide application pendency, EVC status, undertaking compliance, document validity, overdue/escalated matters and regional performance reports. |
| Undertakings and renewals | Merged into a generic obligation or proposed as wholly separate engines. | Provide distinct business records/views while sharing evidence, review, timer and audit infrastructure. |
| Obligation status | Overdue and escalated were mixed into review states. | Separate review lifecycle, time condition and escalation history; an overdue response can remain under review. |
| Renewal validity | Uploading renewed evidence could be mistaken for fulfillment. | Retain current accepted evidence and its expiry while reviewing replacements. Upload does not extend validity. |
| Document applicability | All records were tied to a new approval case and a mandatory expiry timestamp. | Allow institution/asset validity records linked to relevant cases. Use applicable date rules and manual resolution for missing or uncertain dates. |
| Certificate dates | Fixed cycles risked being generalized across document types. | Apply the relevant source and issuer rule. Do not generalize the structural-stability five-year cycle to fire certificates. |
| Signatures | Blanket existing Class-3 DSC pre-verification was asserted. | Distinguish cryptographic integrity, issuer authorization, revocation and compliance. Apply document-specific signature requirements and allowed manual/source verification. |
| EVC timing | A single appointment slot or two underspecified deadlines. | Track queue, readiness, scheduling, confirmation, planned/actual visit, report submission and acceptance separately, with prescribed clock origins. |
| New-institution scheduling | Suggested automatic P0 priority and a three-times penalty. | Track new-institution timelines explicitly; use only authorized priorities and benchmark their effect. No invented numeric weight. |
| Online and offline modes | Physical travel could dominate the scheduling pitch. | Respect the applicable online process. Activate offline travel constraints only when an offline mode is authorized. |
| Committee authority | A planner could be interpreted as selecting committee membership. | Use authorized membership/rosters and permitted choices. Do not replace mandated selection procedures. |
| Booking integrity | Date-only proposals and committee-level availability. | Use actual time intervals; check individual member conflicts across committees and reserve resources atomically on confirmation. |
| Solver outcomes | Optimality could be claimed from any generated schedule. | Distinguish FEASIBLE, OPTIMAL, INFEASIBLE, UNKNOWN and MODEL_INVALID. Optimality concerns only the encoded model. |
| Escalation | Four tiers with 24-hour/seven-day thresholds presented as fixed. | Use approved, versioned triggers, recipients and calendars. Illustrative values are not universal AICTE timelines. |
| Clocks | Aggregate excluded pause seconds could obscure their origin. | Preserve original receipt, individual authorized pause intervals, deadline history, calendar and timezone basis. |
| Notifications | Acknowledgement could be confused with compliance closure. | Keep delivery/acknowledgement separate from verified fulfillment; deduplicate, retry and expose failures. |
| Schema blueprint | Standalone SQL was treated as an executable complete solution. | Specify ownership constraints, same-case transition links, guarded revision updates, policy publication controls, evidence lineage, access policies and booking protections before implementation. |
| OCR | The existing extraction foundation was described as a complete renewal pre-check. | Require PDF rasterization for image OCR, page-level handling of mixed documents and explicit unavailability/abstention when OCR cannot operate. |
| AI role | Summaries and prediction could be interpreted as binding or already validated. | AI creates reviewable drafts with source references; deterministic rules and authorized people retain control. Prediction requires suitable logs and local evaluation. |
| Evidence of optimization | A six-case fixture and illustrative savings could become impact claims. | Treat the fixture as a demonstration. Compare credible baselines on held-out scenarios and measure actual user effort and errors. |
| Implementation status | Reusable evidence infrastructure could be mistaken for new-statement delivery. | Label new approval, obligation, scheduling and domain-report modules as proposed until their code and end-to-end checks establish otherwise. |
| Research claims | Global novelty and a guaranteed finale advantage. | State a focused integration thesis; distinguish public evidence, design recommendations, open questions and measured results. |

## Consolidated proposed solution

Revised solution for SIH26262

### Integrated AICTE Approval Workflow Automation, Compliance Monitoring and Alert Management System

30 October 2026 | Solution specification and research references

**From pending files to verified action**

Build one workbench that explains the next permitted action for every approval case, tracks continuing conditions until verified closure, and helps officials schedule eligible committee appointments. Every action has an owner, evidence, a deadline basis and a recorded outcome.

### The three essential outcomes

- **Case movement:** advance only through an applicable, approved route; explain blockers and record returns with reasons.
- **Continuing compliance:** keep undertakings and document renewals visible after the application decision when they remain applicable.
- **Operational planning:** recommend appointments within authorized choices and expose capacity shortages instead of concealing them.

### What this version corrects

It makes case summaries, role-specific views, separate undertaking and renewal views, EVC milestones and consolidated reports explicit. It removes unsupported completion percentages, universal route mappings, automatic three-times scheduling weights and fixed escalation timings presented as official rules.

### Evidence and status

The public problem statement and handbook define the domain boundary [1,2]. The proposed product behavior in this PDF is a design recommendation. It is not proof of implementation, production integration, legal certification or competition success. Generic file tracking already exists in government systems [3]. The differentiator must be the demonstrated integration and measured execution quality.

## Approval routing and case summaries

Select a valid route, then enforce its permitted transitions.

Support the route families named in the statement: Only Scrutiny, Scrutiny + EVC, EVC + SAC/SHC, Only EVC and other authorized combinations [1]. These are configuration capabilities, not a basis for inventing category-to-route rules.

| Route family | Required product behavior |
| --- | --- |
| Only Scrutiny | Complete the applicable scrutiny path and authorized handoff without inserting an unnecessary EVC. |
| Scrutiny + EVC | Place the case in the EVC queue only when the applicable preliminary conditions are satisfied. |
| EVC + SAC/SHC | Support the applicable hearing or appeal branch. Keep SAC and SHC as distinct steps with their own triggers and actors. |
| Only EVC and other routes | Allow a directly authorized inspection route or another approved combination without fabricating a scrutiny prerequisite. |

### Deterministic route selection

A versioned decision table evaluates application category, requested changes, academic cycle, relevant orders and later stage outcomes. It returns a route and the supporting rule. Unknown or conflicting inputs create a review task. Do not assume that all ordinary EoA cases require scrutiny, or that a hearing and an appeal are interchangeable.

### Guard every transition

A command checks the actor, assignment, current case revision, required evidence, prior outcomes and allowed next step. Record the previous and new state, reason, source rule and timestamp in one transaction. Reject stale or duplicate commands safely. Record automated transitions under a traceable service identity.

### Govern policy changes

A process pack contains route graphs, selection rules, calendars, deadlines, templates, escalation rules, source locators and approval history. Require independent publication approval. Pin running cases to a version; migrate only through an explicit, tested and authorized action.

### Electronic case summary and standard communications

Generate a dated dossier containing profile, route/version, stage history, clocks, findings, evidence references, EVC milestones and open obligations. Offer governed templates for deficiency, scheduling, hearing and reminder communications. Separate drafting, authorization, issue and delivery. Viewing a summary must not issue an official notice.

Policy boundary: APH clauses 1.8-1.10 describe applicable committee selection and competent-authority decisions [2]. The software supports those responsibilities; it does not acquire them.

## Role based workspaces and reporting

One consistent case record with server-enforced scope.

| Role | Visible information and permitted work |
| --- | --- |
| Institution representative | Own institution only: case progress, recorded requests, permitted responses, undertakings, renewal evidence and applicable review paths. |
| Assigned committee member | Assigned cases and relevant evidence; committee observations and permitted report actions. Distinguish scrutiny, EVC, SHC and SAC responsibilities. |
| Regional officer | Authorized regional pendency, ageing, assignments, EVC milestones, approaching dates and unresolved escalations. |
| Bureau officer | Authorized cross-region summaries, workload and bottlenecks; consolidated reports with controlled drill-down. |
| Competent authority | Cases ready for an authorized decision and escalations requiring direction, with complete supporting history. |

### Dashboard content

Display counts by stage, institution, region and responsible actor; distinguish eligible work, blocked work, unassigned cases and completed cases. Show total elapsed time, stage age, due-date basis, outstanding requests and workload. Make ageing buckets configurable and label the calendar used.

### Six report families

- Application pendency and stage ageing.
- EVC status, scheduling delays and report completion.
- Undertaking submissions and verification status.
- Lease and prescribed document validity and renewals.
- Overdue items, escalation ownership and unresolved follow-up.
- Region-wise processing performance with case-mix context.

### Reporting integrity

Every export records its filters, authorization scope, generation time, data snapshot and policy/calendar versions. Use a shared source for dashboard totals and exports. Reconcile totals against underlying cases. Show data freshness rather than calling every view real time. Compare regions with context; raw closure counts alone can reward premature closure or penalize complex workloads.

## Undertakings and document renewals

Use distinct views while sharing evidence and verification infrastructure.

### Time-bound undertaking record

Store the originating approval/order, exact condition and source location, institution, required action, responsible person, reviewer, evidence requirement, due-date basis and applicability. A condition is created only from an authorized source; an AI draft does not create an active duty.

### Document validity record

Store document type, institution and relevant asset/site, issuing authority, issue date, verified validity basis, current accepted evidence version, replacement submissions and review outcomes. Link related cases without requiring a new approval case for every existing institution record.

| Dimension | Recommended representation |
| --- | --- |
| Review lifecycle | Open; evidence submitted; under review; verified closed; disputed; cancelled with authority and reasons. |
| Time condition | Upcoming, due or overdue is calculated separately from review status. An overdue submission can still be under review. |
| Escalation | Separate escalation events and ownership. Escalation does not replace the review state. |
| Renewal continuity | Retain the previous accepted document and its expiry while reviewing a replacement. An upload does not extend validity. |

### Correct date handling

The handbook provides a structural-stability requirement after thirty years from the Completion Certificate and a five-year validity for that certificate; it also requires a valid Fire Safety Certificate [2, clause 6.17(h)-(i)]. Do not assign a universal five-year expiry to fire certificates. Apply the relevant issuer and policy basis. For leases, check the applicable remaining-duration requirement as well as nominal expiry.

### Submission and verification

Scan and quarantine uploads; check evidence lineage, extracted entity/date fields and applicable authenticity mechanisms. Unsigned documents need the document-specific rule and permitted verification path, not automatic rejection. Preserve original bytes, reviewer corrections and superseded versions. Closure requires an authorized reviewer and a supported disposition.

A signature integrity result does not by itself establish an authorized issuer, current revocation status or regulatory compliance. Do not claim blanket Class-3 DSC validation for every lease, certificate or undertaking.

## Dates alerts and escalation

Every deadline must have a source and every escalation must have an owner.

### Three separate measurements

| Clock | Meaning and control |
| --- | --- |
| Total elapsed time | Time since original receipt. Preserve it across returns, transfers, pauses and policy changes. |
| Accountable processing time | An operational measure with only expressly authorized exclusions. Store each pause interval, reason, source, actor and evidence. |
| Obligation deadline | A condition or renewal date independent of application closure. Retain its history and authorized extensions. |

### Deadline calculation

Record the initiating event, date/time rule, calendar version, timezone, due date and rule/order source. Distinguish a date-only expiry from a precise appointment timestamp. Specify whether a rule uses calendar days, working days or an issuing authority date. A missing or conflicting date creates a review task rather than an invented deadline.

### Configurable reminder and escalation policy

For each stage or obligation, configure the trigger basis, recipient roles, jurisdiction, channel, repeat rule, business calendar, escalation destination, suppression condition and authorized acknowledgement/closure behavior. Version the policy with its approval record.

An illustrative ladder is advance reminder, assigned-owner follow-up, regional escalation and bureau/competent-authority direction. Timing and recipients must come from authorized policy. Values such as 90/60/30/7 days, 24 hours or seven days are examples only, not verified universal AICTE requirements.

### Reliable delivery and deadline changes

- Deduplicate by resource, event type, policy version and deadline generation. Cancel or supersede obsolete jobs after an authorized change.
- Write notification intent and the related state change transactionally; retry delivery with idempotency and expose terminal failures.
- Distinguish queued, dispatched, delivered where evidenced, failed and acknowledged. An acknowledgement is not compliance verification.
- Retain audit events for reminder creation, dispatch, escalation, reassignment, deadline extension and resolution.

An overdue alert does not automatically authorize rejection, suspension or a show-cause notice. Route the matter to the responsible official with its evidence. Technical delivery is not necessarily proof of legal service.

## EVC planning within authorized constraints

Improve appointment feasibility without replacing mandated committee selection.

Use authorized membership/rosters and permitted appointment choices. The handbook describes online committee proceedings in its applicable Chapter 1 process, with offline proceedings under exceptional circumstances [2]. Include travel constraints only for an authorized offline mode.

### Track milestones separately

Record queue entry, readiness confirmation, scheduling target, appointment confirmation, planned start/end, actual completion, report submission, sign-off/acceptance and any cancellation or rebooking. Track time to schedule and time to complete/report separately. Each deadline needs its own prescribed starting event; do not assume every report clock starts at confirmation.

### Hard constraints

- Applicable prerequisites and authorized route; eligible, authorized committee membership.
- Availability, duration, no member double booking across committees, conflicts of interest and permitted mode.
- Required institutional readiness and any mandatory case ordering.
- For offline work only: feasible travel and site constraints where applicable.

### Optimization objectives

Within permitted discretion, compare plans by late/unassigned cases, lateness, excessive waiting, repeated deferral and avoidable rescheduling. Agree the hierarchy with the process owner. Track new-institution timelines explicitly; the statement does not establish an automatic P0 rank or three-times penalty. Avoid starving older or less flexible eligible cases.

### Use the simplest method that works

First implement an earliest-deadline baseline with deterministic handling of scarce eligible slots. Evaluate CP-SAT only when larger, varied tests justify the additional complexity [4,5]. The existing six-case synthetic fixture is a demonstration, not evidence of general superiority or real-world savings.

### Feasibility and confirmation

Display FEASIBLE versus proven OPTIMAL for the encoded model. Preserve UNKNOWN and MODEL_INVALID as distinct outcomes [5]. Show unassigned cases and diagnostic reasons when no acceptable slot is found; do not relax eligibility silently. Label diagnostic explanations honestly unless formally established by the solver. Recheck constraints atomically at confirmation because concurrent bookings can invalidate a proposal.

## Architecture and data integrity

Reuse the evidence backend and add explicit approval-domain records.

| Layer | Responsibilities |
| --- | --- |
| User workspaces | Institution response, assigned committee review, regional work queue, bureau reporting and competent-authority decisions. |
| Application services | Authorized commands, route guards, obligation review, booking confirmation, summaries and exports. |
| Deterministic policy | Versioned routes, selection rules, clocks, calendars, escalation recipients and communication templates. |
| Durable background work | Existing workflow infrastructure and outbox for timers, extraction, notifications and bounded planning jobs. |
| Storage | PostgreSQL for transactional records; protected object storage for original evidence, derivatives and report snapshots. |

### Core records

Approval case; published process-pack version; stage attempt; transition event; deadline and pause history; undertaking; document validity record; evidence submission and verification event; authorized roster; member availability; appointment proposal and confirmed booking; alert, escalation and notification event; case-summary/report snapshot.

### Required invariants

- An application, case, institution and evidence version must agree on ownership. Enforce foreign keys and ownership relationships, not comments naming a relationship.
- A transition references stage attempts belonging to the same case. Revision checks require an atomic compare-and-update, not only a stored expected revision.
- A published pack requires approval and a frozen content hash. Existing cases keep a recoverable version reference.
- A verified closure requires a reviewer, evidence/disposition and time. Deadline changes preserve earlier values and reasons.
- A confirmed booking reserves all necessary members for an actual time interval. Prevent overlapping confirmations transactionally.

### Cost and implementation discipline

Retain FastAPI, PostgreSQL, object storage and the existing workflow/outbox foundation where their contracts fit. Keep clear modules in one backend before introducing separate services. Avoid a platform rewrite, blockchain or an LLM route engine. Database tables alone do not implement authorization, workflows, reporting or correctness.

## Bounded AI and ethical safeguards

Make review authority and failure handling visible in the product.

### Useful AI assistance

Optionally extract draft conditions, responsible entities and dates from an order, with exact page/paragraph evidence. A reviewer checks each draft before it creates an active obligation or deadline. Show corrections and unresolved ambiguity. Keep all essential workflows available when AI is unavailable.

### Extraction reliability

Rasterize scanned PDF pages before invoking an image OCR provider. Handle mixed digital/scanned documents page by page. Missing OCR models must create a visible unavailable/manual-review outcome; synthetic test text must never be presented as recognized real evidence. Evaluate entity, action and date errors separately. Low-quality scans and contradictory dates need explicit abstention.

### Decision authority

Do not allow the assistant to select binding policy, publish a process pack, issue an official order, extend deadlines, approve an institution or close an obligation. Document text is untrusted data, including any embedded instructions. Limit tool access and keep model-generated text outside deterministic authorization checks.

| Safeguard | Required behavior |
| --- | --- |
| Due process | Show reasons and evidence; support permitted correction, hearing and appeal paths; preserve human responsibility for decisions. |
| Fairness | Use published operational criteria. Examine repeated deferral and waiting-time disparities with eligibility and case-type context; avoid opaque institution risk labels. |
| Privacy | Limit collected data and retention; restrict rows, fields, downloads and exports by assignment and jurisdiction; protect storage and transport. |
| Auditability | Record source versions, human changes, issue/delivery events and privileged access. Protect history and monitor changes; do not call ordinary logs tamper-proof. |
| Accessible use | Keyboard-accessible actions, clear errors, recoverable uploads, saved progress and comprehensible explanations. |

These controls are informed by NIST AI RMF 1.0, including GOVERN 3.2 [6]. That framework is voluntary guidance, not Indian legal certification. Learned delay prediction remains future work until suitable authorized historical logs and local validation exist [7].

## Prototype and delivery plan

Prove one complete vertical slice before expanding policy coverage.

### Six connected screens

| Screen | Essential demonstration |
| --- | --- |
| Work queue | Role-scoped cases, stages, owners, clocks, blockers, ageing and due actions. |
| Case workspace | Explained route/version, evidence, permitted transitions, recorded returns and a case summary. |
| Compliance ledger | Separate undertaking and document-validity tabs; submission, review, renewal and continuing obligations. |
| EVC planner | Eligible queue, milestone dates, constraints, proposals, unassigned reasons and confirmed bookings. |
| Process configuration | Draft/test/publish rules, calendar and escalation preview with independent authorization. |
| Audit and reporting | Traceable history and the six report families with reproducible filters and snapshots. |

### Build sequence

**First:** validate one bounded route and the role model; implement guarded movement, returns and summary generation. **Second:** add undertaking and renewal review with authoritative dates and continuing visibility. **Third:** connect durable reminders, escalation ownership and reports. **Fourth:** implement the scheduling baseline and milestone tracking. Add solver or AI assistance only after their benefit and failure behavior are tested.

### Five-minute demonstration

- Open a blocked case and explain who must act and why.
- Submit institution evidence; show that submission alone does not clear the condition.
- Verify the response and advance only to a permitted next step.
- Show an EVC appointment conflict, an explained alternative or unassigned outcome, and confirmation.
- Finish the application decision while an applicable continuing obligation remains visible; advance the demo clock to trigger follow-up.
- Open the full action history, role-restricted view and consolidated report.

Label demo policies, sample timelines, synthetic institutions and mocked integrations clearly. The earlier evidence-workbench implementation is reusable groundwork; it is not evidence that the new SIH26262 approval modules have already been delivered.

## Validation and measurable success

Establish correctness before claiming efficiency.

| Area | Acceptance evidence |
| --- | --- |
| Routing | Approved examples for every supported family; permitted and prohibited transitions; returns, hearing/appeal distinctions and unknown-category handling. |
| Dates and alerts | Calendar/timezone boundaries, date-only expiry, authorized pauses/extensions, obsolete timer cancellation, retries and missed-delivery visibility. |
| Obligations | Upload does not close a condition; review rejection is retained; application closure preserves continuing duties; pending renewal does not extend an expired document. |
| Scheduling | No hard-constraint violation; individual member overlap checks; stale proposal/conflicting confirmation rejection; cancellations and impossible-capacity scenarios. |
| Permissions | Cross-institution, cross-region and unassigned-committee access attempts fail, including exports and document downloads. |
| Durability | Worker restart, duplicate message and replay tests preserve outcomes without duplicate bookings, notices or closures. |
| Reports | All six report types reconcile with source records and preserve scope, filters, source versions and generation time. |

### Benchmark design

Compare FIFO where permitted, earliest-deadline, scarcity-aware earliest-deadline and CP-SAT on identical cases and constraints. Include scarce eligibility, clustered deadlines, cancellations, high load and insufficient capacity. Hold out scenarios from tuning. Report late/unassigned cases, lateness, maximum wait, repeated deferral, rescheduling, runtime and solver status/bounds.

For user effort, compare equivalent tasks on a baseline and prototype with consenting users, counterbalanced order and reported sample size, errors and uncertainty. For extraction, use independently annotated held-out documents and report wrong/omitted dates, reviewer corrections and review time. Research papers do not supply the prototype's accuracy.

### Permitted pitch

Say: "Designed to reduce missed obligations and avoidable waiting, with authorized human decisions and traceable evidence." Publish numerical savings only after measuring them. No desk research can establish an 88% completion score, a guaranteed win or a universal market gap. Validate policy coverage with the process owner and current amendments before operational use.

## Research references for the PPT

Exact links and the claims they can support.

PPT use: place the relevant source number next to the supported claim and reproduce its full reference on the reference slide. Separate verified source facts, proposed design choices and measured prototype results. Sources reviewed on 30 October 2026.

### [1] Smart India Hackathon. SIH 2026 Problem Statements, SIH26262.

[Open the exact source](https://www.sih.gov.in/sih2026PS)

**URL:** https://www.sih.gov.in/sih2026PS

Use for scope and stated prototype/evaluation expectations. It does not establish a numerical scoring rubric, API access or completion percentage.

### [2] AICTE. Approval Process Handbook 2024-25 to 2026-27.

[Open the exact source](https://www.aicte.gov.in/sites/default/files/APH%20Final.pdf)

**URL:** https://www.aicte.gov.in/sites/default/files/APH%20Final.pdf

Relevant locators: clauses 1.8-1.10, printed pp. 7-8 (PDF pages 23-24); clause 6.17(h)-(i), printed p. 57 (PDF page 73). Baseline source; review applicable later amendments before activating policy.

### [3] NIC Udupi. NIC page, eOffice section and Salient Features.

[Open the exact source](https://udupi.nic.in/en/nic/)

**URL:** https://udupi.nic.in/en/nic/

Supports the existing availability of government electronic approval/file exchange and MIS capabilities. Does not prove other systems lack the proposed combination.

### [4] Perron, L., Didier, F. and Gay, S. (2023). The CP-SAT-LP Solver (Invited Talk). LIPIcs CP 2023, 3:1-3:2.

[Open the exact source](https://doi.org/10.4230/LIPIcs.CP.2023.3)

**URL:** https://doi.org/10.4230/LIPIcs.CP.2023.3

Primary technical publication. A short invited-talk paper, not an AICTE scheduling trial or a source of local savings estimates.

### [5] Google OR-Tools. CP-SAT Solver, CP-SAT return values.

[Open the exact source](https://developers.google.com/optimization/cp/cp_solver)

**URL:** https://developers.google.com/optimization/cp/cp_solver

Supports feasible/proven-optimal/infeasible/unknown distinctions. It does not establish correctness or optimality beyond the encoded model.

### [6] NIST (2023). Artificial Intelligence Risk Management Framework, AI RMF 1.0. NIST AI 100-1.

[Open the exact source](https://doi.org/10.6028/NIST.AI.100-1)

**URL:** https://doi.org/10.6028/NIST.AI.100-1

Sections 3.1-3.7 and GOVERN 3.2 support responsible-AI design and oversight. Voluntary guidance; not Indian statutory authority.

### [7] Tax, N., Verenich, I., La Rosa, M. and Dumas, M. Predictive Business Process Monitoring with LSTM Neural Networks. 2016 preprint, revised 2017.

[Open the exact source](https://arxiv.org/abs/1612.02130)

**URL:** https://arxiv.org/abs/1612.02130

Supports the historical-log basis for predictive monitoring and the need for dataset-specific evaluation; not accuracy on AICTE records.

## Recommended acceptance and handoff

Before marking this proposed solution implemented, demonstrate all of the following against a supported, policy-reviewed route:

- An unauthorized or stale transition is rejected; a permitted transition records its evidence and reason.
- A submitted response remains open until an authorized reviewer accepts it.
- An obligation survives application closure where applicable.
- An expired document remains expired while an unverified renewal is pending.
- A deadline change preserves the old date and suppresses obsolete reminders.
- Conflicting appointment confirmations cannot double-book a member.
- Institution and region boundaries also apply to exports and evidence downloads.
- All six domain reports reconcile with the same case and obligation records.
- Model and OCR failures lead to visible review handling, not false verification.
- Synthetic demonstrations, mock integrations and measured production results are clearly distinguished.

**Build decision:** deliver the deterministic case-and-obligation workflow first, reliable dates and reporting second, and evaluated scheduling assistance third. Add optional AI only when its evidence and failure handling justify it.
