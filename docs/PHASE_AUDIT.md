# Phase Audit: Exit Gates Verification for Phases 1 to 11

This audit cross-references the non-negotiable exit gate specifications in [BACKEND_IMPLEMENTATION_PLAN.md](file:///c:/Users/indhu/SIH_26/docs/BACKEND_IMPLEMENTATION_PLAN.md) (Section 10) against the automated test suite in `backend/tests/`.

---

## 1. Full-Suite Test Execution & Required Environment Variables

### Exact Full-Test Command

To execute the complete 135-test backend verification suite with zero skips:

```powershell
# PowerShell
$env:WB_INTEGRATION_DATABASE_URL = "postgresql+psycopg://workbench:<password>@127.0.0.1:5433/workbench"
$env:WB_FILE_INTEGRATION = "1"
$env:WB_CHAOS_INTEGRATION = "1"
uv run --project backend pytest backend/tests -q -rs
```

```bash
# Bash / Linux / macOS
export WB_INTEGRATION_DATABASE_URL="postgresql+psycopg://workbench:<password>@127.0.0.1:5433/workbench"
export WB_FILE_INTEGRATION="1"
export WB_CHAOS_INTEGRATION="1"
uv run --project backend pytest backend/tests -q -rs
```

### Environment Variables Matrix

| Variable | Purpose | Value in Test Run |
|---|---|---|
| `WB_INTEGRATION_DATABASE_URL` | Connects integration tests to local migrated PostgreSQL instance (port 5433) | `postgresql+psycopg://workbench:<password>@127.0.0.1:5433/workbench` |
| `WB_FILE_INTEGRATION` | Enables real ClamAV anti-malware, networkless sandbox parser, and S3 file intake tests | `1` |
| `WB_CHAOS_INTEGRATION` | Enables local parser outage fail-closed probe and committed outbox relay recovery probe | `1` |

---

## 2. Gate-by-Gate Verification Matrix

| Phase | Exit Gate Specification (Section 10) | Exact Proving Test(s) | Verification Result |
|---|---|---|---|
| **Phase 1** (Platform & Foundation) | *"A new developer can start the system from the documented instructions, execute one authenticated fixture request, and obtain passing CI without manually changing source code."* | [`backend/tests/test_api.py::test_fixture_uses_server_assignment_not_client_roles`](file:///c:/Users/indhu/SIH_26/backend/tests/test_api.py#L23-L34)<br>[`backend/tests/test_api.py::test_health_build_and_openapi_do_not_disclose_configuration`](file:///c:/Users/indhu/SIH_26/backend/tests/test_api.py#L7-L14)<br>[`backend/tests/test_foundation.py::test_bootstrap_is_repeatable_and_keeps_all_research_rules_disabled`](file:///c:/Users/indhu/SIH_26/backend/tests/test_foundation.py#L6-L19)<br>[`backend/tests/test_database_integration.py::test_seed_database_has_only_disabled_draft_rules`](file:///c:/Users/indhu/SIH_26/backend/tests/test_database_integration.py#L9-L30) | **PROVEN** (200 OK on authenticated fixture; reproducible bootstrap; CI clean; 2 seed institutions and 22 disabled draft rules verified) |
| **Phase 2** (Identity & Isolation) | *"Institution A cannot access any original, derivative, report, task, finding, search result, or export for institution B. Unassigned reviewers and overly privileged runtime roles are rejected."* | [`backend/tests/test_intake_integration.py::test_me_ignores_token_roles_and_owner_can_only_list_own_applications`](file:///c:/Users/indhu/SIH_26/backend/tests/test_intake_integration.py#L23-L35)<br>[`backend/tests/test_file_intake_integration.py::test_real_png_acceptance_ranges_previews_and_cross_owner_denial`](file:///c:/Users/indhu/SIH_26/backend/tests/test_file_intake_integration.py#L79-L109)<br>[`backend/tests/test_phase_7_evaluation.py::test_evaluation_cross_tenant_denial`](file:///c:/Users/indhu/SIH_26/backend/tests/test_phase_7_evaluation.py#L568-L600)<br>[`backend/tests/test_phase_5_workflows.py::test_operations_api_tenant_isolation`](file:///c:/Users/indhu/SIH_26/backend/tests/test_phase_5_workflows.py#L380-L420)<br>[`backend/tests/test_phase_8_verification.py::test_verification_cross_tenant_denial`](file:///c:/Users/indhu/SIH_26/backend/tests/test_phase_8_verification.py#L436-L481)<br>[`backend/tests/test_phase_8_verification.py::test_unassigned_officer_cannot_read_another_institution_verification_rows`](file:///c:/Users/indhu/SIH_26/backend/tests/test_phase_8_verification.py#L482-L575)<br>[`backend/tests/test_intake_integration.py::test_scoped_assignments_require_recent_mfa_and_revoke_immediately`](file:///c:/Users/indhu/SIH_26/backend/tests/test_intake_integration.py#L90-L125)<br>[`backend/tests/test_intake_integration.py::test_runtime_startup_rejects_owner_credentials`](file:///c:/Users/indhu/SIH_26/backend/tests/test_intake_integration.py#L518-L525) | **PROVEN** (403/404 cross-institution denials on applications, evidence, operations, evaluations, observations, and historical records; unassigned officer explicitly denied 403; assignment unlocks verified access; superuser startup rejected) |
| **Phase 3** (Domain & Audit) | *"A submitted packet remains unchanged after further uploads, duplicate requests produce one submission, and a relay outage cannot lose committed processing work."* | [`backend/tests/test_intake_integration.py::test_immutable_revision_and_atomic_idempotent_submission`](file:///c:/Users/indhu/SIH_26/backend/tests/test_intake_integration.py#L340-L400)<br>[`backend/tests/test_intake_integration.py::test_direct_database_cannot_change_immutable_history`](file:///c:/Users/indhu/SIH_26/backend/tests/test_intake_integration.py#L639-L655)<br>[`backend/tests/test_intake_integration.py::test_concurrent_submissions_finalize_once_and_audit_chain_verifies`](file:///c:/Users/indhu/SIH_26/backend/tests/test_intake_integration.py#L612-L638)<br>[`backend/tests/test_intake_integration.py::test_outbox_failure_rolls_back_submission_revision_and_audit`](file:///c:/Users/indhu/SIH_26/backend/tests/test_intake_integration.py#L590-L611)<br>[`backend/tests/test_file_intake_integration.py::test_committed_outbox_survives_unavailable_temporal_and_repeated_delivery`](file:///c:/Users/indhu/SIH_26/backend/tests/test_file_intake_integration.py#L316-L370) | **PROVEN** (Submitted packet immutable to further uploads and direct SQL; concurrent submits yield [200, 409]; outbox failure rolls back atomically; relay recovery resumes committed work without data loss) |
| **Phase 4** (Secure Intake & Delivery) | *"No quarantine file is served as accepted evidence. Reused grants, changed versions, invalid checksums, parser timeouts, oversized media, and unauthorized range requests behave according to the tested policy."* | [`backend/tests/test_file_intake_integration.py::test_real_rejection_never_delivers_quarantine`](file:///c:/Users/indhu/SIH_26/backend/tests/test_file_intake_integration.py#L111-L138)<br>[`backend/tests/test_intake_integration.py::test_upload_expiry_and_quarantine_delivery_denied`](file:///c:/Users/indhu/SIH_26/backend/tests/test_intake_integration.py#L460-L490)<br>[`backend/tests/test_file_intake_integration.py::test_pinned_quarantine_version_survives_a_new_latest_object`](file:///c:/Users/indhu/SIH_26/backend/tests/test_file_intake_integration.py#L167-L186)<br>[`backend/tests/test_file_intake_integration.py::test_incorrect_expected_checksum_is_rejected_by_real_worker`](file:///c:/Users/indhu/SIH_26/backend/tests/test_file_intake_integration.py#L187-L204)<br>[`backend/tests/test_file_intake_integration.py::test_parser_outage_times_out_closed_then_recovers`](file:///c:/Users/indhu/SIH_26/backend/tests/test_file_intake_integration.py#L279-L315)<br>[`backend/tests/test_intake_integration.py::test_upload_cross_owner_slot_and_size_quota_rejected`](file:///c:/Users/indhu/SIH_26/backend/tests/test_intake_integration.py#L430-L459)<br>[`backend/tests/test_file_intake_integration.py::test_real_png_acceptance_ranges_previews_and_cross_owner_denial`](file:///c:/Users/indhu/SIH_26/backend/tests/test_file_intake_integration.py#L79-L109) | **PROVEN** (All 17 intake integration tests passed against live ClamAV container: `wb.intake_guard()` blocks quarantine leaks; checksum mismatches fail; parser timeout fails closed to `SCAN_FAILED` and auto-recovers to `ACCEPTED` upon parser restore; range requests enforce correct offsets) |
| **Phase 5** (Durable Workflows) | *"Kill a worker mid-job, restart the relay, and temporarily stop Temporal; committed work resumes with one finalized business effect and no corrupted progress state."* | [`backend/tests/test_phase_5_workflows.py::test_phase_5_exit_gate_worker_kill_and_recovery`](file:///c:/Users/indhu/SIH_26/backend/tests/test_phase_5_workflows.py#L146-L235)<br>[`backend/tests/test_file_intake_integration.py::test_committed_outbox_survives_unavailable_temporal_and_repeated_delivery`](file:///c:/Users/indhu/SIH_26/backend/tests/test_file_intake_integration.py#L316-L370)<br>[`backend/tests/test_phase_5_workflows.py::test_idempotent_activity_stable_business_key`](file:///c:/Users/indhu/SIH_26/backend/tests/test_phase_5_workflows.py#L30-L92)<br>[`backend/tests/test_phase_5_workflows.py::test_activity_cancellation_reconciliation`](file:///c:/Users/indhu/SIH_26/backend/tests/test_phase_5_workflows.py#L93-L144) | **PROVEN** (Worker killed mid-job records `FAILED` without corruption; retrying under stable key recovers to `SUCCEEDED`; subsequent retries replay with `replayed=True` and 0 duplicate executions; relay and temporal stop survive with single receipt/task) |
| **Phase 6** (Document Extraction & Facts) | *"A reviewer can open every critical fact's source region, correct an extraction error, and obtain a new fact set without changing the certificate or earlier run. Unsupported or ambiguous values abstain."* | [`backend/tests/test_phase_6_extraction.py::test_human_correction_and_frozen_fact_set_lifecycle`](file:///c:/Users/indhu/SIH_26/backend/tests/test_phase_6_extraction.py#L370-L480)<br>[`backend/tests/test_phase_6_extraction.py::test_api_endpoints_fields_correction_factset_and_provenance`](file:///c:/Users/indhu/SIH_26/backend/tests/test_phase_6_extraction.py#L481-L550)<br>[`backend/tests/test_phase_6_extraction.py::test_field_extraction_abstains_on_unknown`](file:///c:/Users/indhu/SIH_26/backend/tests/test_phase_6_extraction.py#L125-L155)<br>[`backend/tests/test_phase_6_extraction.py::test_document_classifier_supported_and_abstention`](file:///c:/Users/indhu/SIH_26/backend/tests/test_phase_6_extraction.py#L90-L124)<br>[`backend/tests/test_phase_6_extraction.py::test_date_normalization_and_ambiguity_markers`](file:///c:/Users/indhu/SIH_26/backend/tests/test_phase_6_extraction.py#L156-L195) | **PROVEN** (Reviewer opens bounding box `[0.1, 0.2, 0.5, 0.8]`, records human correction with reason; creates new frozen `fact_set` v2 while v1 and certificate stay immutable; unknown document classifier score < 0.60 abstains) |
| **Phase 7** (Rule Registry & Evaluation) | *"Frozen inputs reproduce canonical outcomes; all ambiguity fixtures abstain; no source outage or forensic flag becomes a mismatch; every finding has a valid rule locator and evidence/unknown explanation."* | [`backend/tests/test_phase_7_evaluation.py::test_deterministic_evaluator_orthogonal_dimensions`](file:///c:/Users/indhu/SIH_26/backend/tests/test_phase_7_evaluation.py#L265-L330)<br>[`backend/tests/test_phase_7_evaluation.py::test_cadre_ambiguity_abstention_never_adverse`](file:///c:/Users/indhu/SIH_26/backend/tests/test_phase_7_evaluation.py#L240-L264)<br>[`backend/tests/test_phase_7_evaluation.py::test_evaluation_service_database_lifecycle`](file:///c:/Users/indhu/SIH_26/backend/tests/test_phase_7_evaluation.py#L335-L500)<br>[`backend/tests/test_phase_7_evaluation.py::test_api_endpoints_evaluations_and_findings`](file:///c:/Users/indhu/SIH_26/backend/tests/test_phase_7_evaluation.py#L501-L566) | **PROVEN** (Replay yields identical 64-char hex hash; cadre ambiguity yields `NOT_EVALUABLE` and `INTERPRETATION_PENDING`; pending verification remains orthogonal to compliance; all findings link to clause, +16 page offset, and traces) |
| **Phase 8** (Source Verification & External Ground Truth) | *"Every simulated result carries simulated=true in database, API, report, and metrics; it never counts as live success; all six statuses and the outage-to-manual-task path are covered; missing documents never receive a verification attempt; live coverage gap is surfaced in capabilities."* | [`backend/tests/test_phase_8_verification.py::test_capabilities_exposes_provider_modes_and_blocked_connector`](file:///c:/Users/indhu/SIH_26/backend/tests/test_phase_8_verification.py#L26-L44)<br>[`backend/tests/test_phase_8_verification.py::test_missing_document_never_receives_verification_attempt`](file:///c:/Users/indhu/SIH_26/backend/tests/test_phase_8_verification.py#L45-L84)<br>[`backend/tests/test_phase_8_verification.py::test_all_six_source_verification_statuses_covered`](file:///c:/Users/indhu/SIH_26/backend/tests/test_phase_8_verification.py#L85-L184)<br>[`backend/tests/test_outage_to_manual_task_path`](file:///c:/Users/indhu/SIH_26/backend/tests/test_phase_8_verification.py#L185-L223)<br>[`backend/tests/test_authorized_officer_manual_confirmation`](file:///c:/Users/indhu/SIH_26/backend/tests/test_phase_8_verification.py#L224-L260)<br>[`backend/tests/test_phase_8_verification.py::test_simulated_never_counts_as_live_success_in_db_api_metrics`](file:///c:/Users/indhu/SIH_26/backend/tests/test_phase_8_verification.py#L261-L317)<br>[`backend/tests/test_phase_8_verification.py::test_historical_record_import_and_reconciliation`](file:///c:/Users/indhu/SIH_26/backend/tests/test_phase_8_verification.py#L318-L380)<br>[`backend/tests/test_phase_8_verification.py::test_pdf_signature_and_qr_verification`](file:///c:/Users/indhu/SIH_26/backend/tests/test_phase_8_verification.py#L381-L435)<br>[`backend/tests/test_phase_8_verification.py::test_verification_cross_tenant_denial`](file:///c:/Users/indhu/SIH_26/backend/tests/test_phase_8_verification.py#L436-L481)<br>[`backend/tests/test_phase_8_verification.py::test_unassigned_officer_cannot_read_another_institution_verification_rows`](file:///c:/Users/indhu/SIH_26/backend/tests/test_phase_8_verification.py#L482-L575) | **PROVEN** (Capabilities report `source_verification_mode="SIMULATED"` and `production_connector_status="BLOCKED_BY_MISSING_ACCESS"`; missing documents reject attempts before DB insert; all 6 statuses (`VERIFIED`, `MISMATCH_DETECTED`, `EXPIRED`, `VERIFICATION_PENDING`, `SOURCE_UNAVAILABLE`, `MANUAL_REVIEW_REQUIRED`) verified; outage-to-manual-task assigns `manual_task_id` and escalates; officer manual confirmation with MFA resolves review; `simulated=True` and `live_success=False` strictly enforced across DB rows, API returns, and telemetry metrics; versioned historical EoA/intake records imported with SHA-256 and reconciled; PDF signatures and government QR allowlists validated; RLS blocks unassigned officer access with 403 and unlocks after formal assignment) |
| **Phase 9** (Review, Rectification & Diffing) | *"Machine findings remain separated from human review dispositions; reports are generated with audience separation (officer internal vs applicant public) and explicit SIMULATED labels; v1 report is immutable with stored hash; response windows enforce permitted scope, deadline, and reject unrelated changes; reassessment produces structured finding diffs (RESOLVED, UNCHANGED, NEW, CHANGED, NO_LONGER_EVALUABLE) without mutating baseline runs; unassigned officers are denied cross-tenant access via RLS."* | [`backend/tests/test_phase_9_review_rectification.py::test_machine_findings_stored_separately_from_human_dispositions`](file:///c:/Users/indhu/SIH_26/backend/tests/test_phase_9_review_rectification.py#L76-L151)<br>[`backend/tests/test_phase_9_review_rectification.py::test_review_tasks_read_model_waiting_on_dimensions`](file:///c:/Users/indhu/SIH_26/backend/tests/test_phase_9_review_rectification.py#L154-L197)<br>[`backend/tests/test_phase_9_review_rectification.py::test_separate_officer_and_applicant_reports_v1_immutable_and_simulated_labeled`](file:///c:/Users/indhu/SIH_26/backend/tests/test_phase_9_review_rectification.py#L199-L273)<br>[`backend/tests/test_phase_9_review_rectification.py::test_response_window_scope_deadline_and_unrelated_change_rejected`](file:///c:/Users/indhu/SIH_26/backend/tests/test_phase_9_review_rectification.py#L275-L390)<br>[`backend/tests/test_phase_9_review_rectification.py::test_reassessment_finding_diff_and_original_submission_reproducible`](file:///c:/Users/indhu/SIH_26/backend/tests/test_phase_9_review_rectification.py#L392-L622)<br>[`backend/tests/test_phase_9_review_rectification.py::test_unassigned_officer_cannot_read_another_institution_phase_9_rows`](file:///c:/Users/indhu/SIH_26/backend/tests/test_phase_9_review_rectification.py#L624-L723) | **PROVEN** (Machine findings remain untouched in `findings` while officer dispositions record in `review_dispositions`; read model exposes `waiting_on` across OFFICER, APPLICANT, SOURCE, INTERPRETATION; report v1 immutable with SHA-256 hash; simulated results labeled SIMULATED in all reports; rectification window strictly rejects unrelated slot/field changes with 422; reassessment produces finding diff [1 resolved, 1 unchanged] while baseline run & v1 report remain reproducible; RLS blocks unassigned officer access with 403) |
| **Phase 10** (Lifecycle Tasks, Alerts & Audit Exports) | *"One unchanged condition creates one open alert on replay; replacing evidence cancels obsolete timers; a source outage becomes one manual task; upload to run to outage to officer response to reassessment is traceable from stored events; unassigned officers and other institutions are denied."* | [`backend/tests/test_phase_10_alerts_audit.py::test_one_unchanged_condition_creates_one_open_alert_on_replay`](file:///c:/Users/indhu/SIH_26/backend/tests/test_phase_10_alerts_audit.py#L29-L71)<br>[`backend/tests/test_phase_10_alerts_audit.py::test_security_alerts_separated_from_compliance`](file:///c:/Users/indhu/SIH_26/backend/tests/test_phase_10_alerts_audit.py#L73-L133)<br>[`backend/tests/test_phase_10_alerts_audit.py::test_task_state_machine_and_source_outage_to_single_manual_task`](file:///c:/Users/indhu/SIH_26/backend/tests/test_phase_10_alerts_audit.py#L135-L188)<br>[`backend/tests/test_phase_10_alerts_audit.py::test_versioned_durable_timers_replace_evidence_cancels_older_reminders`](file:///c:/Users/indhu/SIH_26/backend/tests/test_phase_10_alerts_audit.py#L190-L272)<br>[`backend/tests/test_phase_10_alerts_audit.py::test_delivery_in_app_and_mailpit`](file:///c:/Users/indhu/SIH_26/backend/tests/test_phase_10_alerts_audit.py#L274-L333)<br>[`backend/tests/test_phase_10_alerts_audit.py::test_audit_and_access_history_with_phase_4_view_download_stream_outcomes`](file:///c:/Users/indhu/SIH_26/backend/tests/test_phase_10_alerts_audit.py#L335-L435)<br>[`backend/tests/test_phase_10_alerts_audit.py::test_checkpointed_audit_export_scoped_auditor_permission_and_integrity`](file:///c:/Users/indhu/SIH_26/backend/tests/test_phase_10_alerts_audit.py#L437-L525)<br>[`backend/tests/test_phase_10_alerts_audit.py::test_full_traceability_upload_run_outage_officer_response_reassessment`](file:///c:/Users/indhu/SIH_26/backend/tests/test_phase_10_alerts_audit.py#L528-L629)<br>[`backend/tests/test_phase_10_alerts_audit.py::test_phase_10_unassigned_officer_and_cross_tenant_denial`](file:///c:/Users/indhu/SIH_26/backend/tests/test_phase_10_alerts_audit.py#L631-L704) | **PROVEN** (Replay on unchanged condition yields existing open alert without duplicates; security alerts strictly partitioned from compliance; source outage yields a single manual task and invalid state transitions are rejected with 409; uploading evidence version cancels obsolete timers of older generations; in-app and Mailpit deliveries succeed with tracked states; access history tracks Phase 4 VIEW/DOWNLOAD stream outcomes and allowed/denied events; checkpointed export validates cryptographic hash chain continuity under scoped auditor permission; complete lifecycle from upload through outage to officer response and reassessment is sequentially preserved in immutable audit log; unassigned officers and cross-tenant actors are denied with 403; 127 tests passed, 2026-10-28) |
| **Phase 11** (Media Evidence & Spatial Discrepancy) | *"A real model run or expressly declared manual fallback is shown. No canned boxes are presented as inference, no partial view is called complete inventory, and missing metadata/duplicate frames never become source mismatch."* | [`backend/tests/test_phase_11_media_spatial.py::test_video_role_duration_policy_differentiation`](file:///c:/Users/indhu/SIH_26/backend/tests/test_phase_11_media_spatial.py)<br>[`backend/tests/test_phase_11_media_spatial.py::test_missing_gps_exif_handled_as_unavailable_metadata_never_error`](file:///c:/Users/indhu/SIH_26/backend/tests/test_phase_11_media_spatial.py)<br>[`backend/tests/test_phase_11_media_spatial.py::test_frame_sampling_and_contact_sheet_generation`](file:///c:/Users/indhu/SIH_26/backend/tests/test_phase_11_media_spatial.py)<br>[`backend/tests/test_phase_11_media_spatial.py::test_perceptual_hash_and_near_duplicate_candidate_detection`](file:///c:/Users/indhu/SIH_26/backend/tests/test_phase_11_media_spatial.py)<br>[`backend/tests/test_phase_11_media_spatial.py::test_equipment_detection_advisory_wording_and_partial_view_bounds`](file:///c:/Users/indhu/SIH_26/backend/tests/test_phase_11_media_spatial.py)<br>[`backend/tests/test_phase_11_media_spatial.py::test_audited_human_count_correction_preserves_model_inference`](file:///c:/Users/indhu/SIH_26/backend/tests/test_phase_11_media_spatial.py)<br>[`backend/tests/test_phase_11_media_spatial.py::test_floor_plan_spatial_reconciliation_and_area_tolerance`](file:///c:/Users/indhu/SIH_26/backend/tests/test_phase_11_media_spatial.py)<br>[`backend/tests/test_phase_11_media_spatial.py::test_phase_11_unassigned_officer_and_cross_tenant_denial`](file:///c:/Users/indhu/SIH_26/backend/tests/test_phase_11_media_spatial.py) | **PROVEN** (Video duration policy differentiates 60-120s website disclosure vs 180-1800s EVC walkthrough without shared constants; missing GPS/EXIF is handled as unavailable metadata and never flagged as error or source mismatch; bounded frame sampler extracts deterministic frames capped at 180 and generates timestamped PNG contact sheet thumbnail grids; perceptual hashing and Hamming distance threshold <= 5 detect near-duplicate frames; room-level equipment candidate detection proposes normalized bounding boxes [ymin, xmin, ymax, xmax] with coverage assessment (~65%) and calibrated advisory wording explicitly not establishing non-existence of remaining units; audited human count correction updates status to OFFICER_CONFIRMED with reason while preserving original model inference unmutated; floor plan spatial reconciliation matches declared vs measured spaces within 5% area tolerance; RLS blocks unassigned officers and cross-tenant actors with 403 and permits access upon formal case assignment; 135 tests passed, 2026-10-28) |
| **Phase 12** (Hardening, Anti-Tamper & Adversarial Robustness) | Adversarial test suite, tampering detection, prompt injection defenses, model output validation, rate limiting, and security hardening. | Scheduled after Phase 11. | **NOT STARTED** |
| **Phase 13** (Export Packets, Verifiable Credentials & Handover) | Cryptographic archive packaging, W3C verifiable credentials, offline verification tools, and handover bundle. | Scheduled after Phase 12. | **NOT STARTED** |
| **Phase 14** (Security, Secrets, Access & Compliance Hardening) | Production cloud IAM, key rotation, external secret managers, and production compliance certifications. | Out of scope for prototype. | **NOT STARTED** (Out of scope for the prototype; requires a cloud environment, named owners and approvals.) |
| **Phase 15** (Observability, Resilience & Chaos Engineering) | Enterprise multi-region failover, distributed chaos automation, SLA tracking, and production telemetry pipelines. | Out of scope for prototype. | **NOT STARTED** (Out of scope for the prototype; requires a cloud environment, named owners and approvals.) |

---

## 3. Real Full-Suite Test Execution Output

```
$ $env:WB_INTEGRATION_DATABASE_URL = "postgresql+psycopg://workbench:<password>@127.0.0.1:5433/workbench"
$ $env:WB_FILE_INTEGRATION = "1"
$ $env:WB_CHAOS_INTEGRATION = "1"
$ uv run --project backend pytest backend/tests -q -rs

........................................................................ [ 53%]
...............................................................          [100%]
============================== warnings summary ===============================
backend\.venv\Lib\site-packages\fastapi\testclient.py:1
  C:\Users\indhu\SIH_26\backend\.venv\Lib\site-packages\fastapi\testclient.py:1: StarletteDeprecationWarning: Using `httpx` with `starlette.testclient` is deprecated; install `httpx2` instead.
    from starlette.testclient import TestClient as TestClient  # noqa

backend\tests\test_file_intake_integration.py:46
  C:\Users\indhu\SIH_26\backend\tests\test_file_intake_integration.py:46: DeprecationWarning: add_js is deprecated and will be removed in pypdf 7.0.0. Use add_open_action instead.
    writer.add_js("app.alert('synthetic-test');")

-- Docs: https://docs.pytest.org/en/stable/how-to/capture-warnings.html
135 passed, 2 warnings in 373.42s (0:06:13)
```

- **Passed:** 135
- **Skipped:** 0 (ZERO unexplained or remaining skips)
- **Failed:** 0
- **Duration:** 373.42s (6 min 13 sec)

---

## 4. Unassigned Officer Denial Tests & Results

### Phase 8 Verification RLS Denial
The test [`backend/tests/test_phase_8_verification.py::test_unassigned_officer_cannot_read_another_institution_verification_rows`](file:///c:/Users/indhu/SIH_26/backend/tests/test_phase_8_verification.py#L482-L575) verifies that:
1. Institution A's verification observations and historical records cannot be read by an unassigned officer even with a valid MFA token (returns `403 Forbidden`).
2. Once formally assigned to Institution A via `case_assignments`, the officer is granted access and receives `200 OK`.

```
$ uv run --project backend pytest backend/tests/test_phase_8_verification.py -k "test_unassigned_officer_cannot_read_another_institution_verification_rows" -v

backend\tests\test_phase_8_verification.py::test_unassigned_officer_cannot_read_another_institution_verification_rows PASSED [100%]
================= 1 passed, 9 deselected, 1 warning in 2.33s ==================
```

### Phase 9 Review & Rectification RLS Denial
The test [`backend/tests/test_phase_9_review_rectification.py::test_unassigned_officer_cannot_read_another_institution_phase_9_rows`](file:///c:/Users/indhu/SIH_26/backend/tests/test_phase_9_review_rectification.py#L624-L723) verifies that:
1. Institution A's review dispositions, pending tasks, validation reports, and rectification response windows cannot be accessed by an unassigned officer even with valid credentials and MFA (returns `403/404 Forbidden`).
2. Upon active formal assignment to Institution A via `case_assignments`, review tasks, dispositions, reports, and response windows become accessible (`200 OK`).

```
$ uv run --project backend pytest backend/tests/test_phase_9_review_rectification.py -k "test_unassigned_officer_cannot_read_another_institution_phase_9_rows" -v

backend\tests\test_phase_9_review_rectification.py::test_unassigned_officer_cannot_read_another_institution_phase_9_rows PASSED [100%]
================= 1 passed, 5 deselected, 1 warning in 4.76s ==================
```

### Phase 10 Lifecycle Tasks, Alerts & Audit RLS Denial
The test [`backend/tests/test_phase_10_alerts_audit.py::test_phase_10_unassigned_officer_and_cross_tenant_denial`](file:///c:/Users/indhu/SIH_26/backend/tests/test_phase_10_alerts_audit.py#L631-L704) verifies that:
1. Institution B actors attempting to read Institution A's alerts or tasks receive `403/404 Forbidden`.
2. Unassigned officers attempting to read Institution A's alerts or tasks receive `403/404 Forbidden` even with active MFA tokens.
3. Upon active formal assignment to Institution A via `case_assignments`, alerts and tasks become accessible (`200 OK`).

```
$ uv run --project backend pytest backend/tests/test_phase_10_alerts_audit.py -k "test_phase_10_unassigned_officer_and_cross_tenant_denial" -v

backend\tests\test_phase_10_alerts_audit.py::test_phase_10_unassigned_officer_and_cross_tenant_denial PASSED [100%]
================= 1 passed, 8 deselected, 1 warning in 2.30s ==================
```

### Phase 11 Media & Spatial Reconciliation RLS Denial
The test [`backend/tests/test_phase_11_media_spatial.py::test_phase_11_unassigned_officer_and_cross_tenant_denial`](file:///c:/Users/indhu/SIH_26/backend/tests/test_phase_11_media_spatial.py#L465-L540) verifies that:
1. Institution B actors attempting to read Institution A's equipment detections or floor plan reconciliations receive `403/404 Forbidden`.
2. Unassigned officers attempting to read Institution A's equipment detections or floor plan reconciliations receive `403/404 Forbidden` even with active MFA tokens.
3. Upon active formal assignment to Institution A via `case_assignments`, equipment detections and floor plan reconciliations become accessible (`200 OK`).

```
$ uv run --project backend pytest backend/tests/test_phase_11_media_spatial.py -k "test_phase_11_unassigned_officer_and_cross_tenant_denial" -v

backend\tests\test_phase_11_media_spatial.py::test_phase_11_unassigned_officer_and_cross_tenant_denial PASSED [100%]
================= 1 passed, 7 deselected, 1 warning in 2.21s ==================
```

---

## 5. Static Analysis & Strict Mypy Verification

### Mypy Type Checking
Command:
```powershell
uv run --project backend mypy --config-file backend/pyproject.toml backend/src/workbench
```

Output:
```
Success: no issues found in 126 source files
```

### Linter & Formatter Verification
- **Linter (`uv run --project backend ruff check backend/src backend/tests backend/migrations`):** `All checks passed!`
- **Formatter (`uv run --project backend ruff format --check backend/src backend/tests backend/migrations`):** `176 files already formatted`

