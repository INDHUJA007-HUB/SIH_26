# SIH26262: PPT and prototype handoff

Prepared 30 October 2026. Read with [the researched solution](SIH26262_REVISED_SOLUTION_AND_RESEARCH.md). All new-statement features below are proposed until implemented and tested. Keep the organizer's prescribed PPT template; the six blocks below are content to place within it, not a claim about the required slide count.

## 1. Title and 30-second opening

**Working product name:** NiyamFlow  
**Subtitle:** AICTE Approval and Compliance Workbench  
**Official statement:** SIH26262 — Integrated AICTE Approval Workflow Automation, Compliance Monitoring and Alert Management System. [Official listing](https://www.sih.gov.in/sih2026PS).

**Opening script:**

“An approval case can be visible on a dashboard and still remain stuck. NiyamFlow shows the exact blocker, responsible actor and permitted next action. It follows each institutional condition through evidence submission and officer verification, and helps officials plan committee work around real constraints. We reuse our evidence backend and focus the new prototype on measurable workflow outcomes.”

Do not describe AICTE's current process as entirely paper-based. Do not present the previous PS26261 document-authentication project as a completed implementation of this statement.

## 2. Six slide-content blocks

### Block 1 — Problem, users and central idea

**Headline:** Every pending case should have a clear next action.

- Users: institution staff, assigned officers, committee coordinators, bureau supervisors and auditors.
- Problem to demonstrate: a case can wait on evidence, review, committee capacity or a continuing condition, each with a different responsible actor.
- Solution: one case workspace connecting status, owner, deadline, evidence and authorized action.

**Visual:** A case card with “blocked by lease review → assigned officer → review due → source evidence.” Use an illustrative synthetic case, not an invented AICTE incident statistic.

### Block 2 — Solution and defensible differentiation

**Headline:** Route the case. Verify the condition. Explain the plan.

- Explained routing: the next step and its guard are visible.
- Verified closure: uploading evidence requests review; it does not automatically fulfil a condition.
- Constraint-aware planning: committee proposals respect authorization, compatibility, availability and conflicts.
- Accountability: show total elapsed time separately from any authorized exclusions and obligation deadlines.

**Competition sentence:** Government file systems, educational accreditation platforms and BPM products already offer many workflow features. Our differentiating proposition is a focused AICTE execution model demonstrated across all three behaviors, with traceable evidence and comparative evaluation.

### Block 3 — Technical approach

**Headline:** Reuse the backend; add the missing approval lifecycle.

**Diagram labels:** institution/officer UI → authenticated commands → PostgreSQL + evidence storage → outbox → durable case/condition workflows → tasks, scheduling proposals and dashboard updates.

- Deterministic guards control transitions and deadlines.
- An officer confirms document-extracted conditions before they become actionable.
- A scheduling heuristic is the baseline; a bounded solver is an extension when justified.
- Existing cases retain their approved process version; updates need a recorded migration decision.

Do not make a chatbot or an architectural logo cloud the main diagram. Show which component handles a user's actual action.

### Block 4 — Feasibility and adoption

**Headline:** A small deployable slice, with explicit integration boundaries.

- Reuse identity, evidence storage, revision history, review, tasks, timers and audit infrastructure.
- Build new approval cases, process templates, obligations, calendar semantics and EVC planning.
- Demonstrate on labeled synthetic cases and a pre-authorized sample roster.
- Begin integration with a validated import/export adapter, then supervised shadow operation, then separately authorized writeback.
- Human officers retain regulatory verification and decisions.

**Risk-to-mitigation examples:** absent source API → labeled adapter; unclear policy → publication blocked; no feasible committee slot → explanation and escalation; model unavailable → structured manual confirmation.

### Block 5 — Evidence and expected impact

**Headline:** Measure better case handling, not hypothetical national savings.

Use three clearly separated rows:

| Label | What can appear |
| --- | --- |
| Existing foundation | The prior backend's recorded test result; identify its original scope |
| Executed synthetic experiment | Six cases, two authorized committees, three days: naive FIFO/EDF each had one late case; scarcity-aware EDF and the exact finite-model optimum had zero |
| Proposed prototype targets | All mandatory routing/deadline/authorization fixtures pass; no hard scheduling conflicts; evaluate active officer-time reduction, targeting 30% only until measured |

The scheduling result is from the supplied reproducible fixture, not a production performance claim. Include the improved heuristic baseline; do not hide that it matched the exhaustive optimum. Do not put “30% achieved,” “99% accuracy” or “nationwide-ready” on a slide without executed evidence.

### Block 6 — Research and demonstration

Use a short citation list with source names and direct URLs: the SIH brief, AICTE APH, NIC eOffice/FPMS, Creatrix's product page, Camunda documentation, and Google's scheduling documentation. The full register is supplied separately.

**Closing script:** “Our demonstration connects a blocked application, a verified response, a feasible committee appointment and a continuing condition. Every action has a responsible actor, a policy basis and an audit record.”

## 3. Prototype screen contracts

### Screen A — Work queue

Top filters: role scope, administrative unit, processing step, due range and blocker type. Main table: institution, case ID, step, age, due instant, blocking reason, next actor and action button. Summary counts drill into real rows and show data freshness. Lead with work to perform rather than decorative charts.

### Screen B — Case workspace

Left: route and stage-attempt timeline. Centre: selected evidence/version and observations. Right: next-action card, deadline basis and role-appropriate command. A blocked button explains the unmet guard. The institution's view shows only its permitted submissions; it cannot see internal notes or another institution's case.

### Screen C — Conditions and renewals

Columns: condition, originating order, responsible party, due basis, submission timing, review state and closure verifier. Provide “submit evidence,” “request clarification,” “verify fulfilment,” “record authorized extension” and “view history” according to role. Upload-only closure must fail.

### Screen D — EVC planner

Show the policy-provided roster, readiness and compatible calendar slots. Display unavailable/conflicted options with reasons. Proposed appointments require confirmation. A cancellation shows what changes and what remains confirmed. An infeasible plan produces an unresolved-work task rather than a fabricated booking.

### Screen E — Process preview

Three bounded sample routes, effective period, source references, transition guard list and test cases. Show before/after impact for a candidate update. Publishing requires a different authorized person. Avoid building a general workflow design platform for the first demo.

### Screen F — History and export

Filter by case, condition, action, actor and time. Link events to evidence versions and command IDs. A readable export summarizes what happened and which items remain open; it does not issue an official approval certificate.

## 4. Synthetic demonstration cases

| Case | Initial condition | Demonstration outcome |
| --- | --- | --- |
| College A | Lease renewal response is requested | Submission creates a new version; authorized review clears the guard; the case becomes ready for its next permitted step |
| College B | Ready for a committee action but has limited compatible slots | Planner avoids a conflicting appointment; staff confirm a feasible proposal or receive a specific infeasibility explanation |
| College C | A continuing condition remains open after an application decision | A labeled demo clock reaches its due instant; one task/escalation is created; application closure has not erased the condition |

Use explicit synthetic-policy labels for all reminder intervals and processing durations. If the demonstration uses time travel, display it. Keep evidence images, API records and displayed counts consistent across all screens.

## 5. Development sequence

The first milestone is submission-ready clarity and one working case, not a claim to have completed a national platform.

| Milestone | Deliverable | Exit check |
| --- | --- | --- |
| M0 — Pitch pivot | New PS identity, product promise, six content blocks and story | Every slide supports the new workflow problem |
| M1 — Core path | Approval case and one process template; real transitions; actor-scoped work queue | A forbidden stage jump and an unauthorized actor are rejected |
| M2 — Verified condition | Source-linked condition, evidence response, review, clocks and escalation | Upload does not close it; valid officer verification does; deadline generations behave correctly |
| M3 — EVC planning | Authorized roster/calendar input, heuristic, proposal and confirmation | No conflicts or disallowed appointments; unmet constraints visible |
| M4 — Governance and branches | Additional templates and independent process-pack publication | Old-case version remains reproducible |
| M5 — Evidence and rehearsal | Baseline comparisons, failure/retry checks and five-minute API-backed story | Recorded metrics match captured test runs; unavailable integrations stay labeled |

For an initial 48-hour push, prioritize M0 plus the M1–M2 vertical slice, and a basic slot-conflict/confirmation path from M3 if the team can complete it. Reach the remaining milestones before making finale-readiness claims. Allocate work by deliverable and actual team availability; this is not an elapsed-time guarantee.

## 6. Five questions to rehearse

**“How is this different from an ERP?”** Existing products already handle records and workflow. Demonstrate the proposed source-bound action, continuing condition and constrained appointment in one case trail.

**“Why AI?”** To draft a condition from a document with a resolvable citation. Show a human correcting or rejecting the draft. AI is not required to execute an approval.

**“What if policy changes?”** A new approved pack applies according to its scope. Existing cases stay pinned unless an authorized migration is reviewed and recorded.

**“What if there is no authorized API?”** The demo uses synthetic/imported records through a labeled adapter. It does not claim a live AICTE connection or bypass portal controls.

**“What have you measured?”** Separate the existing backend results, the small executed scheduling experiment, new routing/clock tests and proposed future targets. Provide denominators, fixtures and limitations.

## 7. Reference links

- [SIH2026 problem statements](https://www.sih.gov.in/sih2026PS)
- [AICTE Approval Process Handbook](https://www.aicte.gov.in/sites/default/files/APH%20Final.pdf)
- [NIC eOffice documentation overview](https://udupi.nic.in/en/nic/)
- [NIC Chittoor FPMS account](https://informatics.nic.in/files/websites/july-2026/chittoor.php)
- [Creatrix accreditation product description](https://www.creatrixcampus.com/accreditation-management-software)
- [Camunda process-version migration](https://docs.camunda.io/docs/components/concepts/process-instance-migration/)
- [Google CP-SAT solver and statuses](https://developers.google.com/optimization/cp/cp_solver)
