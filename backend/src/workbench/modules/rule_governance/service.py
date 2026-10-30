"""Pure service logic for Phase 12 rule governance, impact simulation, dual control,
offline replay verification, and advisory remedy scenarios.
"""

from __future__ import annotations

import hashlib
import json
import math
import uuid
from typing import Any

from workbench.modules.rule_governance.contracts import (
    CandidateRuleChange,
    CandidateStatus,
    DiffOutcome,
    FourGates,
    ReleaseManifest,
    RemedyProposal,
    RemedyType,
    ReplayBundle,
    RunDiff,
    SimulationResult,
)


def compute_canonical_hash(data: Any) -> str:
    """Compute deterministic SHA-256 over canonical JSON representation."""
    canonical_bytes = json.dumps(data, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(canonical_bytes).hexdigest()


class RuleGovernanceService:
    """Orchestrates candidate releases, four-gate validation, dual control,
    reproducible replay bundles, and advisory remedy calculation.
    """

    @staticmethod
    def create_candidate_manifest(
        candidate_code: str,
        academic_cycle: str,
        numeric_academic_year: int,
        effective_date: str,
        submission_date: str,
        evaluation_time: str,
        author_id: str,
        author_identity: str,
        candidate_rules: list[CandidateRuleChange],
        is_hypothetical: bool = False,
    ) -> dict[str, Any]:
        """Create a candidate release manifest in DRAFT state."""
        manifest_data = {
            "candidate_code": candidate_code,
            "target_academic_cycle": academic_cycle,
            "numeric_academic_year": numeric_academic_year,
            "effective_date": effective_date,
            "submission_date": submission_date,
            "evaluation_time": evaluation_time,
            "author_id": author_id,
            "author_identity": author_identity,
            "rules": [r.model_dump() for r in candidate_rules],
            "is_hypothetical": is_hypothetical,
        }
        manifest_hash = compute_canonical_hash(manifest_data)
        return {
            "id": str(uuid.uuid4()),
            "candidate_code": candidate_code,
            "target_academic_cycle": academic_cycle,
            "numeric_academic_year": numeric_academic_year,
            "effective_date": effective_date,
            "submission_date": submission_date,
            "evaluation_time": evaluation_time,
            "author_id": author_id,
            "author_identity": author_identity,
            "approver_id": None,
            "approver_identity": None,
            "status": CandidateStatus.DRAFT.value,
            "four_gates": FourGates().model_dump(),
            "candidate_rules": [r.model_dump() for r in candidate_rules],
            "release_manifest": manifest_data,
            "manifest_hash": manifest_hash,
            "conflicts_detected": [],
            "what_if_banner": True,
            "is_hypothetical": is_hypothetical,
        }

    @staticmethod
    def validate_dual_control(
        author_id: str,
        author_identity: str,
        approver_id: str,
        approver_identity: str,
    ) -> None:
        """Enforce dual control: author and approver must be different identities.
        Blocks same-person alias bypass.
        """
        if author_id == approver_id:
            raise ValueError("Dual control violation: author and approver cannot have the same ID")
        clean_author = author_identity.strip().lower()
        clean_approver = approver_identity.strip().lower()
        if clean_author == clean_approver:
            raise ValueError(
                "Dual control violation: author and approver alias/identity cannot be the same"
            )

    @staticmethod
    def detect_conflicts(
        candidate_rules: list[dict[str, Any]],
        existing_candidate_rules: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        """Detect conflicting changes to the same rule scope."""
        conflicts = []
        existing_map = {r.get("rule_id"): r for r in existing_candidate_rules if r.get("rule_id")}
        for rule in candidate_rules:
            rule_id = rule.get("rule_id")
            if rule_id in existing_map:
                existing = existing_map[rule_id]
                if existing.get("proposed_parameters") != rule.get("proposed_parameters"):
                    conflicts.append(
                        {
                            "rule_id": rule_id,
                            "clause": rule.get("clause", ""),
                            "conflict_type": "CONCURRENT_SCOPE_MODIFICATION",
                            "message": (
                                f"Rule {rule_id} has conflicting parameter proposals "
                                f"with another active candidate."
                            ),
                        }
                    )
        return conflicts

    @staticmethod
    def simulate_candidate_impact(
        candidate_id: str,
        candidate_rules: list[dict[str, Any]],
        frozen_runs: list[dict[str, Any]],
        is_hypothetical: bool = False,
    ) -> SimulationResult:
        """Simulate candidate rules against frozen facts of stored runs.
        Output a diff per run and requirement: UNCHANGED, NEWLY_DEFICIENT, NEWLY_CLEAR,
        NEWLY_NOT_EVALUABLE. Never writes to existing runs, findings, or notices.
        """
        run_diffs: list[RunDiff] = []
        overall_summary = {
            DiffOutcome.UNCHANGED.value: 0,
            DiffOutcome.NEWLY_DEFICIENT.value: 0,
            DiffOutcome.NEWLY_CLEAR.value: 0,
            DiffOutcome.NEWLY_NOT_EVALUABLE.value: 0,
        }

        # Index candidate rules by rule_id
        candidate_rule_map = {r["rule_id"]: r for r in candidate_rules if "rule_id" in r}

        for run in frozen_runs:
            run_id = run["run_id"]
            app_id = run.get("application_id", "")
            facts = run.get("facts", {})
            baseline_outcomes = run.get("requirement_outcomes", {})  # req_id -> outcome

            req_diffs: dict[str, DiffOutcome] = {}
            run_summary = {
                DiffOutcome.UNCHANGED.value: 0,
                DiffOutcome.NEWLY_DEFICIENT.value: 0,
                DiffOutcome.NEWLY_CLEAR.value: 0,
                DiffOutcome.NEWLY_NOT_EVALUABLE.value: 0,
            }

            for rule_id, cand_rule in candidate_rule_map.items():
                baseline_outcome = baseline_outcomes.get(rule_id, "NOT_EVALUABLE")
                params = dict(cand_rule.get("proposed_parameters", {}))
                if cand_rule.get("dsl_expression"):
                    params["dsl_expression"] = cand_rule["dsl_expression"]

                # Evaluate rule using proposed parameters against frozen facts
                simulated_outcome = RuleGovernanceService._evaluate_single_rule(
                    rule_id, params, facts
                )

                if simulated_outcome == baseline_outcome:
                    diff = DiffOutcome.UNCHANGED
                elif simulated_outcome == "DEFICIENT" and baseline_outcome != "DEFICIENT":
                    diff = DiffOutcome.NEWLY_DEFICIENT
                elif simulated_outcome == "PASS" and baseline_outcome == "DEFICIENT":
                    diff = DiffOutcome.NEWLY_CLEAR
                elif simulated_outcome == "NOT_EVALUABLE":
                    diff = DiffOutcome.NEWLY_NOT_EVALUABLE
                else:
                    diff = DiffOutcome.UNCHANGED

                req_diffs[rule_id] = diff
                run_summary[diff.value] += 1
                overall_summary[diff.value] += 1

            run_diffs.append(
                RunDiff(
                    run_id=run_id,
                    application_id=app_id,
                    requirement_diffs=req_diffs,
                    diff_summary=run_summary,
                )
            )

        return SimulationResult(
            candidate_id=candidate_id,
            what_if_banner=True,
            total_runs_simulated=len(frozen_runs),
            diff_summary=overall_summary,
            run_diffs=run_diffs,
            is_hypothetical=is_hypothetical,
        )

    @staticmethod
    def _evaluate_single_rule(rule_id: str, params: dict[str, Any], facts: dict[str, Any]) -> str:
        """Deterministic evaluation of a candidate rule against facts."""
        from workbench.modules.evaluation import RuleEvaluatorDSL

        expression = params.get("dsl_expression")
        if not expression:
            # Demonstration aliases retain explicit parameters but share the production DSL.
            if rule_id == "APH-LAND-001":
                expression = {
                    "operation": "evidence_presence",
                    "field": "certificates",
                    "required_slot": params.get("required_slot", "LAND_USE_CERTIFICATE"),
                }
            elif rule_id == "APH-INFRA-BW-001":
                expression = {
                    "operation": "threshold_lookup",
                    "input_field": "approved_intake",
                    "target_field": "bandwidth_mbps",
                    "tiers": [
                        {"min": 1, "max": 300, "required": params.get("min_bandwidth_mbps", 100)},
                        {"min": 301, "max": 600, "required": params.get("min_bandwidth_mbps", 300)},
                    ],
                }
            elif rule_id == "APH-INFRA-PRINT-001":
                expression = {
                    "operation": "ratio_check",
                    "numerator_field": "printer_count",
                    "denominator_field": "pc_count",
                    "min_ratio": str(params.get("printer_ratio", "0.05")),
                }
            else:
                expression = {
                    "operation": "abstain",
                    "reason": "No approved executable rule expression supplied",
                }
        outcome, _ = RuleEvaluatorDSL().evaluate_rule(
            rule_id, expression, facts, {}, "2026-10-29", params
        )
        return {"PASS": "PASS", "POTENTIAL_DEFICIENCY": "DEFICIENT"}.get(
            outcome.outcome.value, "NOT_EVALUABLE"
        )

    @staticmethod
    def create_published_release_manifest(
        candidate: dict[str, Any],
        approver_id: str,
        approver_identity: str,
        published_at: str,
    ) -> ReleaseManifest:
        """Create signed release manifest after four gates and dual control verification."""
        RuleGovernanceService.validate_dual_control(
            author_id=candidate["author_id"],
            author_identity=candidate["author_identity"],
            approver_id=approver_id,
            approver_identity=approver_identity,
        )

        member_hashes = {}
        for r in candidate.get("candidate_rules", []):
            rule_id = r.get("rule_id", "")
            member_hashes[rule_id] = compute_canonical_hash(r)

        manifest_data = {
            "release_code": candidate["candidate_code"].replace("CANDIDATE", "RELEASE"),
            "academic_cycle": candidate["target_academic_cycle"],
            "numeric_academic_year": candidate["numeric_academic_year"],
            "effective_date": candidate["effective_date"],
            "submission_date": candidate["submission_date"],
            "evaluation_time": candidate["evaluation_time"],
            "author_id": candidate["author_id"],
            "author_identity": candidate["author_identity"],
            "approver_id": approver_id,
            "approver_identity": approver_identity,
            "member_rule_hashes": member_hashes,
            "published_at": published_at,
            "disclaimer": "Reproducing the evaluator does not reproduce a fresh OCR run.",
        }
        manifest_hash = compute_canonical_hash(manifest_data)

        return ReleaseManifest(
            release_code=manifest_data["release_code"],
            academic_cycle=manifest_data["academic_cycle"],
            numeric_academic_year=manifest_data["numeric_academic_year"],
            effective_date=manifest_data["effective_date"],
            submission_date=manifest_data["submission_date"],
            evaluation_time=manifest_data["evaluation_time"],
            author_id=manifest_data["author_id"],
            author_identity=manifest_data["author_identity"],
            approver_id=approver_id,
            approver_identity=approver_identity,
            member_rule_hashes=member_hashes,
            manifest_hash=manifest_hash,
            published_at=published_at,
            disclaimer=manifest_data["disclaimer"],
        )

    @staticmethod
    def calculate_remedy(
        application_id: str,
        finding_id: str,
        rule_id: str,
        clause: str,
        facts: dict[str, Any],
        is_open_window: bool = True,
    ) -> RemedyProposal:
        """Calculate transparent arithmetic remedy scenario for a finding.
        Evaluates remedy on a copy of facts. Strictly advisory, guarantees no approval.
        """
        remedy_id = str(uuid.uuid4())
        remedy_facts = dict(facts)
        calculation_trace: dict[str, Any] = {}

        if rule_id == "APH-LAND-001":
            remedy_type = RemedyType.MISSING_CERTIFICATE
            calculation_trace = {
                "rule_id": rule_id,
                "clause": clause,
                "deficiency": "Missing mandatory Land Use Certificate",
                "required_slot": "LAND_USE_CERTIFICATE",
                "authorized_issuer": "REVENUE_DEPARTMENT",
                "arithmetic": "Supply 1 valid certificate in slot LAND_USE_CERTIFICATE",
            }
            certs = list(remedy_facts.get("certificates", []))
            certs.append({"slot": "LAND_USE_CERTIFICATE", "issuer": "REVENUE_DEPARTMENT"})
            remedy_facts["certificates"] = certs
            findings_closed = ["finding_land_missing_001"]
            findings_remaining: list[str] = []
            allowed = True
            reason = None

        elif rule_id == "APH-INFRA-BW-001":
            remedy_type = RemedyType.BANDWIDTH_TIER
            approved_intake = facts.get("approved_intake", 420)
            current_bw = facts.get("bandwidth_mbps", 100)
            required_bw = 300 if approved_intake > 300 else 100
            shortfall = max(0, required_bw - current_bw)
            calculation_trace = {
                "approved_intake": approved_intake,
                "current_bandwidth_mbps": current_bw,
                "required_bandwidth_mbps": required_bw,
                "bandwidth_shortfall_mbps": shortfall,
                "arithmetic": (
                    f"Intake {approved_intake} requires {required_bw} Mbps. "
                    f"Current {current_bw} Mbps leaves shortfall of {shortfall} Mbps."
                ),
            }
            remedy_facts["bandwidth_mbps"] = required_bw
            findings_closed = ["finding_bandwidth_shortfall_001"]
            findings_remaining = []
            allowed = True
            reason = None

        elif rule_id == "APH-INFRA-PRINT-001":
            remedy_type = RemedyType.PRINTER_SHORTFALL
            pc_count = facts.get("pc_count", 200)
            current_printers = facts.get("printer_count", 6)
            required_printers = math.ceil(pc_count * 0.05)  # 5% of PCs
            shortfall = max(0, required_printers - current_printers)
            calculation_trace = {
                "pc_count": pc_count,
                "ratio": 0.05,
                "required_printers": required_printers,
                "current_printers": current_printers,
                "printer_shortfall": shortfall,
                "arithmetic": (
                    f"5% of {pc_count} PCs = {required_printers} printers required. "
                    f"Current {current_printers} leaves shortfall of {shortfall}."
                ),
            }
            remedy_facts["printer_count"] = required_printers
            findings_closed = ["finding_printer_shortfall_001"]
            findings_remaining = []
            allowed = True
            reason = None

        elif rule_id == "APH-INTAKE-REDUCE-001":
            raise ValueError(
                "Intake optimization requires an independently approved "
                "interpretation and process policy"
            )

        else:
            raise ValueError(f"Unsupported rule for remedy calculation: {rule_id}")

        result = RuleGovernanceService._evaluate_single_rule(rule_id, {}, remedy_facts)
        findings_closed = [finding_id] if result == "PASS" else []
        findings_remaining = [] if result == "PASS" else [finding_id]
        allowed = allowed and is_open_window
        if not is_open_window:
            reason = "No authorized response window is open"

        advisory_wording = (
            "This remedy calculation is advisory and exploratory only. "
            "It does not promise regulatory approval, waive statutory scrutiny, "
            "or modify approved application records."
        )

        return RemedyProposal(
            remedy_id=remedy_id,
            application_id=application_id,
            finding_id=finding_id,
            rule_id=rule_id,
            clause=clause,
            remedy_type=remedy_type,
            is_advisory=True,
            guarantees_approval=False,
            advisory_wording=advisory_wording,
            calculation_trace=calculation_trace,
            proposed_remedy_facts=remedy_facts,
            re_evaluation_result={
                "compliance_status": result,
                "closed_count": len(findings_closed),
                "remaining_count": len(findings_remaining),
            },
            findings_closed=findings_closed,
            findings_remaining=findings_remaining,
            allowed_at_current_stage=allowed,
            stage_restriction_reason=reason,
            is_simulated=True,
        )

    @staticmethod
    def get_amendment_demo_fixture() -> dict[str, Any]:
        """Seed hypothetical scenario: international E&T PG seat capacity changes
        from 15% in base text to 25% in amendment. Approved intake 60, request 12 seats.
        Base capacity: 9 seats (deficient for 12 requested).
        Amendment capacity: 15 seats (clear for 12 requested).
        """
        approved_intake = 60
        requested_seats = 12

        base_pct = 15
        base_capacity = int(approved_intake * (base_pct / 100.0))  # 9
        base_status = "CLEAR" if requested_seats <= base_capacity else "DEFICIENT"

        amend_pct = 25
        amend_capacity = int(approved_intake * (amend_pct / 100.0))  # 15
        amend_status = "CLEAR" if requested_seats <= amend_capacity else "DEFICIENT"

        return {
            "fixture_name": "International E&T PG Seat Capacity Amendment",
            "is_hypothetical": True,
            "is_simulated": True,
            "rule_id": "APH-INTL-PG-001",
            "clause": "Clause 2.15.2 — International Supernumerary Seats",
            "approved_intake": approved_intake,
            "requested_seats": requested_seats,
            "base_policy": {
                "capacity_percentage": base_pct,
                "calculated_capacity": base_capacity,
                "finding_status": base_status,
                "shortfall": max(0, requested_seats - base_capacity),
            },
            "amendment_policy": {
                "capacity_percentage": amend_pct,
                "calculated_capacity": amend_capacity,
                "finding_status": amend_status,
                "shortfall": max(0, requested_seats - amend_capacity),
            },
            "diff_outcome": DiffOutcome.NEWLY_CLEAR.value,
            "screen_notice": (
                "Other conditions are held fixed and not approved by this calculation."
            ),
        }

    @staticmethod
    def build_replay_bundle(
        run_id: str,
        application_id: str,
        facts: dict[str, Any],
        evidence_manifest: dict[str, Any],
        source_observations: list[dict[str, Any]],
        rule_hashes: dict[str, str],
        evaluator_version: str = "1.0.0-phase12",
        evaluation_snapshot: dict[str, Any] | None = None,
        expected_outcomes: list[dict[str, Any]] | None = None,
    ) -> ReplayBundle:
        """Create an offline reproducibility export bundle containing frozen inputs."""
        bundle_id = str(uuid.uuid4())
        files = {
            "facts.json": json.dumps(facts, sort_keys=True, indent=2),
            "evidence_manifest.json": json.dumps(evidence_manifest, sort_keys=True, indent=2),
            "source_observations.json": json.dumps(source_observations, sort_keys=True, indent=2),
            "rule_hashes.json": json.dumps(rule_hashes, sort_keys=True, indent=2),
        }

        if evaluation_snapshot is not None:
            files["evaluation.json"] = json.dumps(
                {"snapshot": evaluation_snapshot, "expected_outcomes": expected_outcomes},
                sort_keys=True,
            )

        file_hashes = {}
        for fname, content in files.items():
            file_hashes[fname] = hashlib.sha256(content.encode("utf-8")).hexdigest()

        manifest = {
            "bundle_id": bundle_id,
            "run_id": run_id,
            "application_id": application_id,
            "evaluator_version": evaluator_version,
            "file_hashes": file_hashes,
        }
        bundle_hash = compute_canonical_hash(manifest)

        return ReplayBundle(
            bundle_id=bundle_id,
            run_id=run_id,
            application_id=application_id,
            bundle_hash=bundle_hash,
            evaluator_version=evaluator_version,
            manifest=manifest,
            files=files,
            file_hashes=file_hashes,
            disclaimer=(
                "Offline replay verification bundle. Reproducing the evaluator "
                "does not reproduce a fresh OCR run."
            ),
        )

    @staticmethod
    def verify_replay_bundle_offline(bundle_data: dict[str, Any]) -> tuple[bool, str | None]:
        """Verify an exported replay bundle offline (no database or network).
        Validates every file hash and the manifest hash.
        Returns (True, None) on clean verification, or (False, error_description) on failure.
        """
        manifest = bundle_data.get("manifest", {})
        expected_bundle_hash = bundle_data.get("bundle_hash", "")
        computed_bundle_hash = compute_canonical_hash(manifest)

        if expected_bundle_hash != computed_bundle_hash:
            return (
                False,
                f"HASH_MISMATCH: bundle_hash expected {expected_bundle_hash} "
                f"but computed {computed_bundle_hash}",
            )

        expected_file_hashes = manifest.get("file_hashes", {})
        files = bundle_data.get("files", {})
        required = {
            "facts.json",
            "evidence_manifest.json",
            "source_observations.json",
            "rule_hashes.json",
        }
        if not isinstance(expected_file_hashes, dict) or not required.issubset(
            expected_file_hashes
        ):
            return False, "INVALID_MANIFEST: required replay files are missing"
        if bundle_data.get("file_hashes") != expected_file_hashes:
            return False, "HASH_MISMATCH: file hashes differ from manifest"
        if not isinstance(files, dict) or set(files) != set(expected_file_hashes):
            return False, "MISSING_FILE: replay file set differs from manifest"

        for fname, expected_hash in expected_file_hashes.items():
            if fname not in files:
                return (
                    False,
                    f"MISSING_FILE: file '{fname}' listed in manifest but missing in bundle",
                )
            content = files[fname]
            if not isinstance(content, str):
                return False, f"INVALID_FILE: {fname} must contain UTF-8 text"
            actual_hash = hashlib.sha256(content.encode("utf-8")).hexdigest()
            if actual_hash != expected_hash:
                return (
                    False,
                    f"HASH_MISMATCH: file '{fname}' expected {expected_hash} "
                    f"but computed {actual_hash}",
                )

        if "evaluation.json" in files:
            from workbench.modules.evaluation import DeterministicEvaluator
            from workbench.modules.rule_registry import RuleVersionRecord

            try:
                payload = json.loads(files["evaluation.json"])
                snapshot = payload["snapshot"]
                result = DeterministicEvaluator().evaluate(
                    institution_id=snapshot["institution_id"],
                    application_id=snapshot["application_id"],
                    application_revision_id=snapshot["application_revision_id"],
                    fact_set_id=snapshot["fact_set_id"],
                    fact_set_hash=snapshot["fact_set_sha256"],
                    facts=snapshot["facts"],
                    claims=snapshot["claims"],
                    rule_release_id=snapshot["rule_release_id"],
                    rule_release_hash=snapshot["rule_release_sha256"],
                    rules=[RuleVersionRecord.model_validate(r) for r in snapshot["rules"]],
                    evaluation_as_of=snapshot["evaluation_as_of"],
                    execution_mode=snapshot["execution_mode"],
                    evidence_manifest=snapshot["evidence_manifest"],
                )
                output_keys = (
                    "rule_id",
                    "outcome",
                    "rationale",
                    "observed_value",
                    "expected_value",
                    "calculation_trace",
                )
                actual = [
                    {k: o.model_dump(mode="json")[k] for k in output_keys} for o in result.outcomes
                ]
                expected = payload["expected_outcomes"]
                if sorted(actual, key=lambda o: o["rule_id"]) != sorted(
                    expected, key=lambda o: o["rule_id"]
                ):
                    return False, "REPLAY_MISMATCH: frozen evaluation outcomes differ"
            except (KeyError, TypeError, ValueError):
                return False, "INVALID_EVALUATION: incomplete frozen inputs"
        return True, None
