"""Phase 7 comprehensive tests for rule registry, deterministic DSL evaluation,
orthogonal dimensions, golden policy vectors, and evaluation HTTP endpoints.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import uuid4

from sqlalchemy import insert, update

from workbench.adapters import tables as t
from workbench.adapters.evaluation_service import EvaluationService
from workbench.adapters.rule_registry_service import RuleRegistryService
from workbench.modules.evaluation.dsl import RuleEvaluatorDSL
from workbench.modules.evaluation.evaluator import DeterministicEvaluator
from workbench.modules.evaluation.models import (
    CompletenessStatus,
    ComplianceOutcome,
    DocumentValidityStatus,
    ForensicConcernStatus,
    SourceVerificationStatus,
)
from workbench.modules.rule_registry.importer import RuleRegistryImporter
from workbench.modules.rule_registry.models import (
    InterpretationState,
)


def test_rule_registry_importer_page_offsets_and_unresolved_abstentions() -> None:
    """Subphase 7.1: Import 22 records with source hashes, +16 page locators,
    and preserve INTERPRETATION_PENDING on unresolved rules.
    """
    importer = RuleRegistryImporter()
    sources = importer.load_sources()
    assert len(sources) >= 4

    u02_source = next((s for s in sources if s.source_code == "U02"), None)
    assert u02_source is not None
    assert u02_source.sha256 == "153d54816f2cf11489218e239113544e8d49b73680009688baa7dc4880636051"

    interpretations, versions, release = importer.load_rules_and_versions()
    assert len(interpretations) == 22
    assert len(versions) == 22
    assert release.release_code == "AICTE-APH-2024-27-SEED"
    assert release.academic_cycle == "2024-27"
    assert release.is_active is True

    # Check page offset (+16 for standard APH U02 rules)
    for v in versions:
        if v.source_id == "U02" and v.printed_page is not None and v.pdf_page is not None:
            assert v.pdf_page - v.printed_page == 16
            assert v.page_offset == 16
        # Invariant: Machine rule versions never allow adverse action
        assert v.adverse_action_allowed is False

    # Check unresolved rules are strictly INTERPRETATION_PENDING
    cadre_interp = next(
        (i for i in interpretations if i.rule_id == "FACULTY.CADRE.AMBIGUITY"), None
    )
    assert cadre_interp is not None
    assert cadre_interp.interpretation_state == InterpretationState.INTERPRETATION_PENDING

    bba_interp = next(
        (i for i in interpretations if i.rule_id == "CATEGORY.BBA_BMS_BCA.2026"), None
    )
    assert bba_interp is not None
    assert bba_interp.interpretation_state == InterpretationState.INTERPRETATION_PENDING

    elp_interp = next((i for i in interpretations if i.rule_id == "ELP.50_PERCENT.CONFLICT"), None)
    assert elp_interp is not None
    assert elp_interp.interpretation_state == InterpretationState.INTERPRETATION_PENDING


def test_dsl_bandwidth_tiers_pass_and_deficiency() -> None:
    """Subphase 7.4: Bandwidth tiers golden test vectors:
    - 301–600 intake requires 300 Mbps
    - Intake 500 with 100 Mbps -> POTENTIAL_DEFICIENCY (delta: -200)
    - Intake 500 with 300 Mbps -> PASS (delta: 0)
    - Intake 500 with 500 Mbps -> PASS (delta: +200)
    """
    dsl = RuleEvaluatorDSL()
    rule_dsl = {
        "operation": "threshold_lookup",
        "input_field": "intake",
        "target_field": "bandwidth_mbps",
        "comparator": "gte",
        "tiers": [
            {"min": 1, "max": 300, "required": 100, "unit": "Mbps"},
            {"min": 301, "max": 600, "required": 300, "unit": "Mbps"},
            {"min": 601, "max": 900, "required": 500, "unit": "Mbps"},
            {"min": 901, "max": 999999, "required": 1000, "unit": "Mbps"},
        ],
        "dimension": "COMPLIANCE",
    }

    # Vector 1: 500 intake, 100 Mbps (Deficient)
    outcome_def, doc_v = dsl.evaluate_rule(
        rule_id="INFRA.BANDWIDTH",
        dsl_expression=rule_dsl,
        facts={"intake": 500, "bandwidth_mbps": 100},
        claims={},
        evaluation_as_of="2026-10-26",
    )
    assert outcome_def.outcome == ComplianceOutcome.POTENTIAL_DEFICIENCY
    assert outcome_def.calculation_trace["delta"] == "-200"
    assert outcome_def.calculation_trace["required_value"] == "300"
    assert outcome_def.calculation_trace["observed_value"] == "100"

    # Vector 2: 500 intake, 300 Mbps (Exact match -> PASS)
    outcome_pass, doc_v = dsl.evaluate_rule(
        rule_id="INFRA.BANDWIDTH",
        dsl_expression=rule_dsl,
        facts={"intake": 500, "bandwidth_mbps": 300},
        claims={},
        evaluation_as_of="2026-10-26",
    )
    assert outcome_pass.outcome == ComplianceOutcome.PASS
    assert outcome_pass.calculation_trace["delta"] == "0"

    # Vector 3: 500 intake, 500 Mbps (Exceeds -> PASS)
    outcome_exceed, doc_v = dsl.evaluate_rule(
        rule_id="INFRA.BANDWIDTH",
        dsl_expression=rule_dsl,
        facts={"intake": 500, "bandwidth_mbps": 500},
        claims={},
        evaluation_as_of="2026-10-26",
    )
    assert outcome_exceed.outcome == ComplianceOutcome.PASS
    assert outcome_exceed.calculation_trace["delta"] == "200"

    # Vector 4: Missing intake -> NOT_EVALUABLE
    outcome_missing, doc_v = dsl.evaluate_rule(
        rule_id="INFRA.BANDWIDTH",
        dsl_expression=rule_dsl,
        facts={"bandwidth_mbps": 500},
        claims={},
        evaluation_as_of="2026-10-26",
    )
    assert outcome_missing.outcome == ComplianceOutcome.NOT_EVALUABLE


def test_dsl_computing_and_printer_ratios() -> None:
    """Subphase 7.4: Computing & printer ratio golden test vectors:
    - Computers 1:6 ratio (min_ratio 0.166667)
    - Printers 1 per 30 computers, min 2 printers
    """
    dsl = RuleEvaluatorDSL()

    comp_dsl = {
        "operation": "ratio_check",
        "numerator_field": "computers",
        "denominator_field": "student_intake",
        "min_ratio": "0.166667",
    }

    # Vector 1: 600 students, 100 computers -> 100/600 = 0.1667 (Pass)
    res_pass, _ = dsl.evaluate_rule(
        rule_id="INFRA.COMPUTERS.DEPARTMENT",
        dsl_expression=comp_dsl,
        facts={"student_intake": 600, "computers": 100},
        claims={},
        evaluation_as_of="2026-10-26",
    )
    assert res_pass.outcome == ComplianceOutcome.PASS

    # Vector 2: 600 students, 80 computers -> 80/600 = 0.1333 (Deficient)
    res_fail, _ = dsl.evaluate_rule(
        rule_id="INFRA.COMPUTERS.DEPARTMENT",
        dsl_expression=comp_dsl,
        facts={"student_intake": 600, "computers": 80},
        claims={},
        evaluation_as_of="2026-10-26",
    )
    assert res_fail.outcome == ComplianceOutcome.POTENTIAL_DEFICIENCY

    printer_dsl = {
        "operation": "ratio_check",
        "numerator_field": "printers",
        "denominator_field": "computers",
        "min_ratio": "0.033333",
        "min_absolute": 2,
    }

    # Vector 3: 90 computers, 3 printers (Passes 1:30 and min 2)
    p_pass, _ = dsl.evaluate_rule(
        rule_id="INFRA.PRINTERS",
        dsl_expression=printer_dsl,
        facts={"computers": 90, "printers": 3},
        claims={},
        evaluation_as_of="2026-10-26",
    )
    assert p_pass.outcome == ComplianceOutcome.PASS

    # Vector 4: 90 computers, 1 printer (Fails min absolute of 2)
    p_fail, _ = dsl.evaluate_rule(
        rule_id="INFRA.PRINTERS",
        dsl_expression=printer_dsl,
        facts={"computers": 90, "printers": 1},
        claims={},
        evaluation_as_of="2026-10-26",
    )
    assert p_fail.outcome == ComplianceOutcome.POTENTIAL_DEFICIENCY


def test_dsl_fire_certificate_valid_and_expired() -> None:
    """Subphase 7.4: Fire certificate date validity test vectors:
    - Review date: 2026-10-26
    - Valid: 2027-05-10 -> VALID_ON_REVIEW_DATE & PASS
    - Expired: 2025-05-10 -> EXPIRED_ON_REVIEW_DATE & POTENTIAL_DEFICIENCY
    """
    dsl = RuleEvaluatorDSL()
    fire_dsl = {
        "operation": "date_validity_check",
        "valid_upto_field": "fire_safety_valid_upto",
        "required_document_type": "FIRE_SAFETY_CERTIFICATE",
    }

    # Valid certificate
    outcome_val, status_val = dsl.evaluate_rule(
        rule_id="DOC.FIRE.VALIDITY",
        dsl_expression=fire_dsl,
        facts={"fire_safety_valid_upto": "2027-05-10"},
        claims={},
        evaluation_as_of="2026-10-26",
    )
    assert outcome_val.outcome == ComplianceOutcome.PASS
    assert status_val == DocumentValidityStatus.VALID_ON_REVIEW_DATE

    # Expired certificate
    outcome_exp, status_exp = dsl.evaluate_rule(
        rule_id="DOC.FIRE.VALIDITY",
        dsl_expression=fire_dsl,
        facts={"fire_safety_valid_upto": "2025-05-10"},
        claims={},
        evaluation_as_of="2026-10-26",
    )
    assert outcome_exp.outcome == ComplianceOutcome.POTENTIAL_DEFICIENCY
    assert status_exp == DocumentValidityStatus.EXPIRED_ON_REVIEW_DATE

    # Missing certificate date
    outcome_mis, status_mis = dsl.evaluate_rule(
        rule_id="DOC.FIRE.VALIDITY",
        dsl_expression=fire_dsl,
        facts={},
        claims={},
        evaluation_as_of="2026-10-26",
    )
    assert outcome_mis.outcome == ComplianceOutcome.POTENTIAL_DEFICIENCY
    assert status_mis == DocumentValidityStatus.UNKNOWN


def test_cadre_ambiguity_abstention_never_adverse() -> None:
    """Subphase 7.4: Unresolved UG faculty cadre ambiguity must abstain (NOT_EVALUABLE)
    and never generate adverse actions.
    """
    dsl = RuleEvaluatorDSL()
    cadre_dsl = {
        "operation": "abstain",
        "reason": "INTERPRETATION_PENDING: Policy ambiguity under review",
    }

    outcome, doc_v = dsl.evaluate_rule(
        rule_id="FACULTY.CADRE.AMBIGUITY",
        dsl_expression=cadre_dsl,
        facts={"professors": 1, "associate_profs": 2, "assistant_profs": 6},
        claims={},
        evaluation_as_of="2026-10-26",
    )
    assert outcome.outcome == ComplianceOutcome.NOT_EVALUABLE
    assert "INTERPRETATION_PENDING" in outcome.rationale


def test_deterministic_evaluator_orthogonal_dimensions() -> None:
    """Subphase 7.2 & 7.3: Verify orthogonal dimensions, manifest hash,
    and adverse_action_allowed=False invariant.
    """
    evaluator = DeterministicEvaluator()
    importer = RuleRegistryImporter()
    _, versions, release = importer.load_rules_and_versions()

    facts = {
        "intake": 400,
        "bandwidth_mbps": 350,
        "computers": 100,
        "student_intake": 500,
        "printers": 4,
        "fire_safety_valid_upto": "2027-10-01",
    }

    result = evaluator.evaluate(
        institution_id=str(uuid4()),
        application_id=str(uuid4()),
        application_revision_id="rev-1",
        fact_set_id="fact-1",
        fact_set_hash="hash-1",
        facts=facts,
        claims={},
        rule_release_id=release.id,
        rule_release_hash=release.content_hash,
        rules=versions,
        evaluation_as_of="2026-10-26",
        evidence_manifest={"missing_slots": []},
    )

    # Invariant: Machine findings NEVER allow adverse actions
    assert result.adverse_action_allowed is False
    for f in result.findings:
        assert f.adverse_action_allowed is False

    # Check 6 orthogonal status dimensions
    assert result.completeness_status == CompletenessStatus.COMPLETE
    assert result.source_verification_status == SourceVerificationStatus.VERIFICATION_PENDING
    assert result.forensic_concern_status == ForensicConcernStatus.NONE_OBSERVED
    assert result.document_validity_status == DocumentValidityStatus.VALID_ON_REVIEW_DATE

    # Manifest hash should be 64-char hex
    assert len(result.manifest_hash) == 64


def test_evaluation_service_database_lifecycle(h) -> None:
    """Test full database lifecycle for Phase 7 evaluations:
    - Seed rules into registry
    - Create institution, application, and frozen FactSet
    - Execute EvaluationService.run_evaluation
    - Verify evaluation_runs, run_inputs, requirement_outcomes, and findings
    """
    inst_id = h.institutions["a"]
    app = h.create(actor="a")
    app_id = app["id"]

    # 1. Seed rules via RuleRegistryService
    rule_service = RuleRegistryService(h.owner)
    release = rule_service.seed_default_rules()
    assert release.release_code == "AICTE-APH-2024-27-SEED"

    # 2. Pre-populate a frozen FactSet with deficient bandwidth
    slot_id = str(uuid4())
    upload_id = str(uuid4())
    ev_ver_id = str(uuid4())
    run_id = str(uuid4())
    field_id_intake = str(uuid4())
    field_id_bw = str(uuid4())
    fact_set_id = str(uuid4())

    with h.owner.begin() as conn:
        conn.execute(
            insert(t.slots).values(
                id=slot_id,
                institution_id=inst_id,
                application_id=app_id,
                code="BANDWIDTH_BILL",
                required=True,
            )
        )
        conn.execute(
            insert(t.uploads).values(
                id=upload_id,
                institution_id=inst_id,
                application_id=app_id,
                slot_id=slot_id,
                actor_id=h.actors["a"],
                filename="bandwidth_bill.pdf",
                media_type="application/pdf",
                expected_size=1024,
                expected_sha256="b" * 64,
                object_key="quarantine/bandwidth_bill.pdf",
                mode="SINGLE",
                part_size=5 * 1024 * 1024,
                status="COMPLETED",
                expires_at=datetime.now(UTC) + timedelta(hours=1),
            )
        )
        conn.execute(
            insert(t.evidence).values(
                id=ev_ver_id,
                institution_id=inst_id,
                application_id=app_id,
                slot_id=slot_id,
                upload_id=upload_id,
                quarantine_key="quarantine/bandwidth_bill.pdf",
                quarantine_version="1",
                sha256="b" * 64,
                media_type="application/pdf",
                filename="bandwidth_bill.pdf",
                size_bytes=1024,
                status="QUARANTINED",
                metadata={"type": "PDF"},
            )
        )
        conn.execute(
            update(t.evidence)
            .where(t.evidence.c.id == ev_ver_id)
            .values(status="ACCEPTED", clean_key="clean/bandwidth_bill.pdf", clean_version="1")
        )
        conn.execute(
            insert(t.extraction_runs).values(
                id=run_id,
                institution_id=inst_id,
                application_id=app_id,
                evidence_version_id=ev_ver_id,
                extractor_version="v1.0",
                document_type="BANDWIDTH_BILL",
                page_count=1,
                status="COMPLETED",
            )
        )
        conn.execute(
            insert(t.extracted_fields).values(
                id=field_id_intake,
                run_id=run_id,
                institution_id=inst_id,
                application_id=app_id,
                evidence_version_id=ev_ver_id,
                field_name="intake",
                field_type="INTEGER",
                raw_value="500",
                normalized_value={"canonical_value": "500"},
            )
        )
        conn.execute(
            insert(t.extracted_fields).values(
                id=field_id_bw,
                run_id=run_id,
                institution_id=inst_id,
                application_id=app_id,
                evidence_version_id=ev_ver_id,
                field_name="bandwidth_mbps",
                field_type="NUMBER",
                raw_value="100",
                normalized_value={"canonical_value": "100"},
            )
        )
        conn.execute(
            insert(t.fact_sets).values(
                id=fact_set_id,
                institution_id=inst_id,
                application_id=app_id,
                version=1,
                canonical_hash="a" * 64,
                is_frozen=True,
            )
        )
        conn.execute(
            insert(t.fact_set_members).values(
                id=str(uuid4()),
                fact_set_id=fact_set_id,
                institution_id=inst_id,
                application_id=app_id,
                field_id=field_id_intake,
                field_name="intake",
                normalized_value={"canonical_value": "500"},
            )
        )
        conn.execute(
            insert(t.fact_set_members).values(
                id=str(uuid4()),
                fact_set_id=fact_set_id,
                institution_id=inst_id,
                application_id=app_id,
                field_id=field_id_bw,
                field_name="bandwidth_mbps",
                normalized_value={"canonical_value": "100"},
            )
        )

    # 3. Execute evaluation via EvaluationService
    eval_service = EvaluationService(h.owner)
    eval_res = eval_service.run_evaluation(
        institution_id=inst_id,
        application_id=app_id,
        evaluation_as_of="2026-10-26",
        execution_mode="DEMONSTRATION",
    )

    assert eval_res["application_id"] == app_id
    assert eval_res["fact_set_id"] == fact_set_id
    assert eval_res["compliance_status"] == ComplianceOutcome.POTENTIAL_DEFICIENCY.value
    assert eval_res["adverse_action_allowed"] is False

    # Check findings generated
    findings = eval_service.get_findings_for_run(eval_res["run_id"])
    assert len(findings) >= 1

    # Find the bandwidth deficiency finding
    bw_finding = next((f for f in findings if f["rule_id"] == "INFRA.BANDWIDTH"), None)
    assert bw_finding is not None
    assert bw_finding["semantic_key"] == "requirement:INFRA.BANDWIDTH:2024"
    assert bw_finding["adverse_action_allowed"] is False
    assert "delta" in bw_finding["calculation_trace"]


def test_api_endpoints_evaluations_and_findings(h) -> None:
    """Test Phase 7 HTTP endpoints with officer credentials:
    - POST /api/v1/applications/{id}/evaluations
    - GET /api/v1/evaluations/{id}
    - GET /api/v1/evaluations/{id}/findings
    - GET /api/v1/findings/{id}/evidence
    """
    inst_id = h.institutions["a"]
    app = h.create(actor="a")
    app_id = app["id"]

    # Pre-seed rules
    rule_service = RuleRegistryService(h.owner)
    rule_service.seed_default_rules()

    # Assign officer to application
    with h.owner.begin() as conn:
        conn.execute(
            insert(t.assignments).values(
                id=str(uuid4()),
                institution_id=inst_id,
                application_id=app_id,
                actor_id=h.actors["officer"],
                access_role="officer",
                expires_at=datetime.now(UTC) + timedelta(days=7),
                granted_by=h.actors["admin"],
                reason="Reviewing compliance evaluation",
            )
        )

    # 1. Trigger evaluation via POST /api/v1/applications/{id}/evaluations
    post_res = h.call(
        "POST",
        f"/api/v1/applications/{app_id}/evaluations",
        actor="officer",
        mfa=True,
        json={"evaluation_as_of": "2026-10-26", "execution_mode": "DEMONSTRATION"},
    )
    assert post_res.status_code == 200, post_res.text
    run_data = post_res.json()
    eval_id = run_data["run_id"]
    assert run_data["adverse_action_allowed"] is False

    # 2. Retrieve evaluation via GET /api/v1/evaluations/{id}
    get_res = h.call("GET", f"/api/v1/evaluations/{eval_id}", actor="officer", mfa=True)
    assert get_res.status_code == 200, get_res.text
    fetched_eval = get_res.json()
    assert fetched_eval["id"] == eval_id
    assert fetched_eval["adverse_action_allowed"] is False
    assert "completeness_status" in fetched_eval
    assert "compliance_status" in fetched_eval

    # 3. Retrieve findings via GET /api/v1/evaluations/{id}/findings
    findings_res = h.call(
        "GET", f"/api/v1/evaluations/{eval_id}/findings", actor="officer", mfa=True
    )
    assert findings_res.status_code == 200, findings_res.text
    findings_list = findings_res.json()
    assert isinstance(findings_list, list)

    if findings_list:
        sample_finding = findings_list[0]
        finding_id = sample_finding["id"]

        # 4. Retrieve finding evidence via GET /api/v1/findings/{id}/evidence
        evidence_res = h.call(
            "GET", f"/api/v1/findings/{finding_id}/evidence", actor="officer", mfa=True
        )
        assert evidence_res.status_code == 200, evidence_res.text
        ev_data = evidence_res.json()
        assert ev_data["finding_id"] == finding_id
        assert "calculation_trace" in ev_data
        assert ev_data["adverse_action_allowed"] is False
