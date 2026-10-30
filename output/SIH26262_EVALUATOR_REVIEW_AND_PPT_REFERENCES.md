# SIH26262: Evaluator Review, Recommended Solution and PPT References

Prepared: 30 October 2026. Project: NiyamFlow.

This is an evaluator-style assessment, not an official SIH assessment. It refines the accompanying complete solution. Where this review differs on scope, metrics or presentation claims, use this review for the PPT. It specifies proposed behavior; it does not establish that the new modules are implemented.

## 1. Recommendation

Build **NiyamFlow: an explainable approval and compliance workbench**.

Its central promise is: **For each case, show the next permitted action, its responsible person, its due date and the evidence needed to complete it. Track continuing conditions until an authorized officer verifies closure.**

From an evaluator's perspective, the strongest submission is a working, policy-faithful demonstration of that promise, with measured results. Adding more AI features does not compensate for incorrect dates, unauthorized transitions or lost obligations. No research establishes that this proposal will win, or that it is globally the most optimized solution.

The recommended scope has three connected parts:

1. Explained case movement through an approved route.
2. An evidence-linked ledger of continuing obligations.
3. Constraint-aware appointment planning for authorized EVC committees.

Dashboards, reminders, access control and audit history support these parts. AI assists document interpretation only when a reviewer can inspect and correct its output.

## 2. What the evidence establishes

### Regulatory baseline

The AICTE handbook describes portal-based committee selection, scrutiny/re-scrutiny, EVC evaluation and competent-authority approval. Chapter 1 also describes online committee proceedings, with offline proceedings under exceptional circumstances. These provisions concern their applicable scope; they are not a universal route for every application category. [AICTE, Approval Process Handbook 2024–25 to 2026–27, clauses 1.8–1.10, printed pages 7–8](https://www.aicte.gov.in/sites/default/files/APH%20Final.pdf#page=23).

**Design inference:** use approved routes and authorized committee rosters. Plan appointment times without replacing mandated membership selection. Make physical-visit travel constraints conditional on an authorized offline mode. Check applicable amendments and process-owner interpretation before activating rules.

### Existing government systems

NIC documents electronic approvals, file exchange, digital signatures, integration and MIS in eOffice. These are established capabilities. [NIC Udupi, eOffice section](https://udupi.nic.in/en/nic/).

**Design inference:** do not pitch file tracking or a pending-count dashboard as an invention. Position NiyamFlow as a focused execution layer whose integrated behavior must be demonstrated and compared. Public documentation does not establish that existing systems lack this combination.

### Optimization research

Perron, Didier and Gay describe the CP-SAT-LP solver in the CP 2023 proceedings. This supports the technical choice of a constraint solver, not an AICTE-specific benefit estimate. Google's documentation distinguishes a feasible solution from one proven optimal for the specified model. [Research publication](https://drops.dagstuhl.de/entities/document/10.4230/LIPIcs.CP.2023.3), [CP-SAT documentation, return values](https://developers.google.com/optimization/cp/cp_solver).

**Design inference:** model policy constraints explicitly, compare a simple scheduling baseline against CP-SAT, and display solver status honestly. A solver cannot fix missing capacity or prove that its model captures every operational concern.

### Predictive monitoring research

Tax and colleagues study predictions from historical process logs; their abstract also identifies sensitivity to the dataset. The paper does not validate a predictor on this project or AICTE records. [Tax et al., 2017 revised manuscript, Predictive Business Process Monitoring with LSTM Neural Networks](https://arxiv.org/abs/1612.02130).

**Design inference:** start with visible elapsed time, deadlines and queue capacity. Introduce learned delay prediction only after obtaining suitable historical logs and evaluating it on later, held-out cases. Do not label a handcrafted priority formula an ML prediction or give it an unvalidated probability.

### Responsible AI guidance

NIST AI RMF 1.0 discusses reliability, transparency, explainability, privacy and harmful bias; GOVERN 3.2 addresses human-AI responsibilities and oversight. This is voluntary design guidance, not Indian statutory authority. [NIST AI 100-1, January 2023, sections 3.1–3.7 and GOVERN 3.2](https://nvlpubs.nist.gov/nistpubs/ai/NIST.AI.100-1.pdf).

**Design inference:** make reviewer correction, accountability, restricted access and failure handling part of the product, rather than an ethics slide alone.

## 3. The optimized solution in practical terms

### A. Case workspace: explain the next permitted action

Each case displays its selected route and version, current stage, blocker, responsible role, required evidence and deadline source. A transition is permitted only if its policy conditions and actor permissions are satisfied. Missing information sends the case to an explained review task.

The displayed explanation should come from structured rules: “Awaiting verification of the institution's response; assigned reviewer must accept or return it with reasons.” An LLM should not invent this explanation or choose a regulatory route.

Do not force all applications through one sequence. For the prototype, choose one clearly bounded application category and validate its route. Show returns, corrections and applicable review paths in that route. Publish a new policy version through an authorized role; do not silently move running cases onto changed rules.

### B. Obligation ledger: response is different from verified completion

Record each obligation separately from the application:

- Originating order and exact document location.
- Applicable institution, responsible person and reviewer.
- Required action, due-date basis and relevant document expiry.
- Submitted evidence version and review history.
- State such as open, response submitted, under review, verified closed or escalated.

These states are proposed product states, not official statutory terminology. A file upload creates a response. Only an authorized verification closes the obligation. A case decision must not delete continuing obligations that remain applicable. A reminder or breach does not itself authorize suspension, rejection or any other adverse action.

### C. Time and alerts: preserve the meaning of dates

Store the event time, the effective due date, the rule/order that created it, the calendar used and any authorized change. Display total elapsed time even if an approved rule excludes some intervals from an operational service clock. These are separate measurements; a system must not quietly reset the original receipt date.

Use deduplicated notification jobs with retry history. Record generated, dispatched and delivered/failed separately where delivery evidence exists. Bundle routine reminders where appropriate, escalate to a named role and show unresolved delivery failures. Notification delivery is not proof of legal service.

Do not fabricate a standard 7/15/30-day legal deadline. Sample deadlines must be visibly marked as demo policy. Extensions require recorded authority and reasons; the software must preserve the earlier due date in history.

### D. EVC planning: optimize only within authorized choices

The planner receives authorized membership/rosters, permitted modes, case readiness, appointment duration, availability, conflicts and relevant due dates. It recommends appointments for confirmation. It cannot substitute members simply to improve its score.

Hard constraints include no double booking, required membership, eligibility, availability, authorized mode and prerequisite completion. Offline travel is considered only where applicable. If a rule mandates case ordering, preserve that ordering.

Use an ordered objective rather than unexplained weights:

1. Satisfy hard constraints and mandatory ordering.
2. Within permitted discretion, reduce late or unassigned eligible cases.
3. Reduce lateness and excessive waiting, subject to published priorities and protection against repeatedly deferring the same cases.
4. Reduce unnecessary rescheduling and other operational costs.

The exact priority hierarchy requires process-owner agreement. Test it on cases where optimizing one objective harms another. Leave cases explicitly unassigned when capacity is insufficient and explain why. A due date must remain visible even when no feasible appointment exists.

First implement an earliest-deadline baseline with deterministic handling of scarce eligible slots. Add CP-SAT only if broader tests show useful gains for acceptable runtime and maintenance cost. Display FEASIBLE, OPTIMAL, INFEASIBLE or UNKNOWN correctly; UNKNOWN does not mean infeasible. Optimality applies only to the encoded objective and constraints.

### E. Bounded AI assistance

An optional assistant can draft structured obligations from an order and highlight the supporting page/paragraph. The reviewer checks the source before activating any obligation, due date or reminder. Low-quality scans, conflicting dates and missing pages go to manual handling.

Treat document contents as untrusted data, including instructions embedded in them. The assistant has no authority to publish policy, grant approval, change a deadline or close an obligation. Keep the workflow usable when the AI service is unavailable. Evaluate dates, responsible entity and required action individually; an overall OCR score is insufficient.

## 4. Ethics expressed as testable behavior

| Concern | Product behavior | Demonstration/check |
| --- | --- | --- |
| Due process | Reasons, source evidence and an applicable correction/review path accompany adverse recommendations. | An officer can reject an incorrect extraction; it never becomes an active condition. |
| Unequal treatment | Queue priorities use authorized operational criteria; avoid institution prestige or opaque institution/officer risk labels. | Compare waiting time and repeated deferral by relevant groups, accounting for case type and eligibility. Investigate disparities rather than assuming equal averages prove fairness. |
| Privacy | Role-scoped records, necessary fields only, protected storage, access history and defined retention. | An institution user cannot retrieve another institution's documents; analytics avoid exposing unnecessary personal details. |
| Human accountability | Named decision-maker and reasons, rather than a generic approval button. | The audit record identifies what the person saw, changed and authorized. |
| Audit integrity | Retain evidence versions and protected change history; monitor privileged changes. | A corrected date keeps the previous value and reason. Do not call an ordinary log tamper-proof. |
| Access and reliability | Clear errors, keyboard-usable screens, upload retry and saved progress. | A failed upload or notification does not silently mark a task complete. |

These are proposed engineering controls informed by the NIST source above. They do not constitute a completed legal compliance certification.

## 5. Implementation scope and cost discipline

Reuse the project's identity, evidence storage/versioning, review tasks, timers and audit infrastructure after checking their contracts. Add explicit approval-case, route-version, obligation and appointment records. Keep one backend with clear modules rather than introducing independent services for every feature.

Use the existing FastAPI/PostgreSQL stack and workflow infrastructure where suitable. Separate deterministic policy execution from optional AI extraction and scheduling. Use an outbox/idempotency mechanism for external effects. Do not replatform solely to add a new orchestration brand.

Build in this order: one validated route and permissions; obligation lifecycle and dates; reliable reminders and history; scheduling baseline; then optional solver/AI if their evidence justifies them. Label mock integrations. Do not imply access to production AICTE APIs without a verified integration agreement.

The earlier backend verification is evidence about the existing codebase, not proof of implementation or correctness of these new SIH26262 modules.

## 6. How to establish improvement without invented percentages

### Correctness before performance

Create a process-owner-reviewed test set of permitted and prohibited transitions, ambiguous orders, deadline changes, role boundaries, duplicate messages, worker restarts and impossible schedules. A plan violating a hard constraint is a failed plan regardless of its speed. Verify outcomes independently of the code that generates them.

### Scheduling benchmark

Compare FIFO where permitted, earliest-deadline, scarcity-aware earliest-deadline and CP-SAT using the same cases, capacity, eligibility and objective definitions. Include low capacity, cancellation, deadline clusters and rare eligible slots. Hold out test scenarios from tuning. Report late and unassigned cases, lateness, maximum waiting time, reschedules, runtime, solver status and bounds/gaps when available. Exact enumeration on small instances can check the solver model.

The repository's six-case synthetic example is a teaching fixture. It does not establish field impact; the simple heuristic already matches the exact optimum on that fixture. Do not use it as evidence that CP-SAT is superior or as the PPT's impact statistic.

### User effort and AI benchmark

With consent, ask comparable users to perform the same defined tasks using a baseline and the prototype; counterbalance order and report errors as well as completion time. Record sample size and uncertainty. For extraction, use independently annotated, held-out documents; report per-field errors, especially wrong or omitted due dates, reviewer corrections and review time. Do not transfer accuracy numbers from another paper or dataset.

Replace earlier illustrative percentage targets with baseline measurements and stakeholder-agreed acceptance thresholds. Until measured, write “intended to reduce missed obligations and avoidable waiting,” not “reduces processing time by 30%.”

## 7. PPT claim-to-source map

Use short source markers on relevant slides and full references on the final slide. Link the exact source, not a search page. Put a section/page alongside regulatory claims.

| Marker / slide | Defensible wording | Exact source | What it does not prove |
| --- | --- | --- | --- |
| [1] Problem alignment | “Designed for SIH26262 approval workflow, compliance and alert management.” | [Official SIH 2026 problem-statement listing](https://www.sih.gov.in/sih2026PS), entry SIH26262 | Production integration access, latest submission availability or a judging score. |
| [2] Process basis | “Our selected route preserves the applicable committee process and competent-authority decisions.” | [AICTE APH 2024–25 to 2026–27](https://www.aicte.gov.in/sites/default/files/APH%20Final.pdf#page=23), clauses 1.8–1.10, printed pp. 7–8; PDF pages 23–24 | That this chapter applies unchanged to every category or incorporates every later amendment. |
| [3] Existing solutions | “Electronic approvals, file movement and MIS are established government capabilities.” | [NIC Udupi: eOffice, Salient Features](https://udupi.nic.in/en/nic/) | Absence of obligation tracking or scheduling in other systems. |
| [4] Scheduling method | “We model permitted scheduling choices using constraint programming.” | [Perron, Didier & Gay, The CP-SAT-LP Solver, CP 2023, 3:1–3:2](https://drops.dagstuhl.de/entities/document/10.4230/LIPIcs.CP.2023.3), DOI 10.4230/LIPIcs.CP.2023.3 | Any specific improvement on AICTE cases. This is a short invited-talk publication, not an AICTE trial. |
| [5] Solver honesty | “The planner reports feasible versus proven-optimal outcomes.” | [Google OR-Tools: CP-SAT Solver, CP-SAT return values](https://developers.google.com/optimization/cp/cp_solver) | Optimality beyond the implemented model or correctness of our model. |
| [6] Responsible AI | “Our design defines human oversight, traceability and privacy controls.” | [NIST, AI RMF 1.0, January 2023](https://nvlpubs.nist.gov/nistpubs/ai/NIST.AI.100-1.pdf), sections 3.1–3.7; GOVERN 3.2 | Indian statutory compliance or that our controls have already passed testing. |
| [7] Future prediction, optional slide | “Historical event logs can support predictive monitoring; local validation is required.” | [Tax, Verenich, La Rosa & Dumas, Predictive Business Process Monitoring with LSTM Neural Networks](https://arxiv.org/abs/1612.02130), 2016 preprint revised 2017; CAiSE 2017 paper | A validated model, accuracy or delay reduction for this project. |

Research access note: the handbook, NIC page, research publications and NIST/Google sources were checked in this review. The SIH listing was available during the earlier project research, but the fresh request in this review returned HTTP 403. Preserve the official brief supplied by the organizer and recheck it before submission; do not represent this review as a successful fresh retrieval of that page.

### Copy-ready reference entries

1. Smart India Hackathon. *SIH 2026 Problem Statements*, SIH26262. https://www.sih.gov.in/sih2026PS
2. AICTE. *Approval Process Handbook 2024–25 to 2026–27*. Clauses 1.8–1.10. https://www.aicte.gov.in/sites/default/files/APH%20Final.pdf
3. NIC Udupi. *NIC — eOffice*, Salient Features. https://udupi.nic.in/en/nic/
4. Perron, L., Didier, F., and Gay, S. (2023). *The CP-SAT-LP Solver (Invited Talk).* LIPIcs CP 2023, 3:1–3:2. https://doi.org/10.4230/LIPIcs.CP.2023.3
5. Google OR-Tools. *CP-SAT Solver*. https://developers.google.com/optimization/cp/cp_solver
6. NIST (2023). *Artificial Intelligence Risk Management Framework (AI RMF 1.0).* NIST AI 100-1. https://doi.org/10.6028/NIST.AI.100-1
7. Tax, N., Verenich, I., La Rosa, M., and Dumas, M. (2017 revised manuscript). *Predictive Business Process Monitoring with LSTM Neural Networks.* https://arxiv.org/abs/1612.02130

## 8. Recommended pitch and demonstration

**Pitch:** “NiyamFlow connects approval-case movement, continuing compliance conditions and eligible committee appointments. Every action has an owner, policy basis, deadline and evidence trail. Officials retain decision authority, while the system exposes blockers and helps plan feasible next steps.”

Demonstrate a blocked case, an institution response, officer verification, the next permitted transition, an obligation continuing after the case decision, and a scheduling conflict with an explained unassigned outcome. Show a corrected AI extraction that never affected the active deadline. End with the actual history and benchmark results, clearly identifying synthetic data.

The defensible differentiator is the demonstrated combination and measured execution quality for a bounded AICTE workflow. Global novelty, user adoption, production integration and real-world savings remain to be established. No officer interviews, controlled user study or real AICTE queue dataset were available for this desk review.
