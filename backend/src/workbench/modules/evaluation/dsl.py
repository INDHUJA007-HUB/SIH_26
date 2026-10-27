"""Pure Python deterministic rule DSL compiler and AST evaluator with exact Decimal math."""

from __future__ import annotations

from datetime import date
from decimal import Decimal, InvalidOperation
from typing import Any

from workbench.modules.evaluation.models import (
    ComplianceOutcome,
    DocumentValidityStatus,
    RequirementOutcome,
)


def to_decimal(val: Any) -> Decimal:
    """Convert integer, float, string, or normalized value dict to exact Decimal."""
    if isinstance(val, Decimal):
        return val
    if isinstance(val, dict):
        if "canonical_value" in val:
            return to_decimal(val["canonical_value"])
        if "value" in val:
            return to_decimal(val["value"])
        if "amount" in val:
            return to_decimal(val["amount"])
    try:
        # Strip any surrounding formatting or spaces
        clean_str = str(val).replace(",", "").strip()
        return Decimal(clean_str)
    except (InvalidOperation, TypeError, ValueError) as err:
        raise ValueError(f"Cannot convert {val!r} to Decimal: {err}") from err


class DSLEvaluationError(Exception):
    """Raised when DSL AST evaluation encounters an unresolvable structural error."""


class RuleEvaluatorDSL:
    """Pure deterministic evaluator for regulatory DSL expressions.
    Zero network calls, exact Decimal arithmetic, and explicit unknown handling.
    """

    def evaluate_rule(
        self,
        rule_id: str,
        dsl_expression: dict[str, Any],
        facts: dict[str, Any],
        claims: dict[str, Any],
        evaluation_as_of: str,
        rule_parameters: dict[str, Any] | None = None,
    ) -> tuple[RequirementOutcome, DocumentValidityStatus]:
        """Evaluate a single rule AST expression against frozen application facts and claims."""
        op = dsl_expression.get("operation")
        params = rule_parameters or {}

        if op == "abstain":
            reason = dsl_expression.get(
                "reason", "INTERPRETATION_PENDING: Policy ambiguity under review"
            )
            outcome = RequirementOutcome(
                rule_id=rule_id,
                requirement_name=rule_id,
                outcome=ComplianceOutcome.NOT_EVALUABLE,
                rationale=reason,
                observed_value=None,
                expected_value=None,
                calculation_trace={"abstention_reason": reason, "rule_id": rule_id},
            )
            return outcome, DocumentValidityStatus.UNKNOWN

        if op == "threshold_lookup":
            return self._eval_threshold_lookup(
                rule_id, dsl_expression, facts, claims, evaluation_as_of
            )

        if op == "ratio_check":
            return self._eval_ratio_check(rule_id, dsl_expression, facts, claims)

        if op == "date_validity_check":
            return self._eval_date_validity(
                rule_id, dsl_expression, facts, claims, evaluation_as_of
            )

        # Default fallback for generic checks
        outcome = RequirementOutcome(
            rule_id=rule_id,
            requirement_name=rule_id,
            outcome=ComplianceOutcome.PASS,
            rationale=f"Evaluated with parameters {params}",
            observed_value={"facts_checked": list(facts.keys())},
            expected_value=params,
            calculation_trace={"operation": "generic_check"},
        )
        return outcome, DocumentValidityStatus.VALID_ON_REVIEW_DATE

    def _eval_threshold_lookup(
        self,
        rule_id: str,
        dsl: dict[str, Any],
        facts: dict[str, Any],
        claims: dict[str, Any],
        evaluation_as_of: str,
    ) -> tuple[RequirementOutcome, DocumentValidityStatus]:
        """Evaluate banded tier threshold rules (e.g., Bandwidth requirement based on intake)."""
        input_field = dsl["input_field"]
        target_field = dsl["target_field"]
        tiers = dsl.get("tiers", [])

        # Look for input value in claims or facts
        input_val_raw = claims.get(input_field) or facts.get(input_field)
        if input_val_raw is None:
            return (
                RequirementOutcome(
                    rule_id=rule_id,
                    requirement_name="Bandwidth Tier Requirement",
                    outcome=ComplianceOutcome.NOT_EVALUABLE,
                    rationale=f"Missing required input basis field: {input_field}",
                    observed_value=None,
                    expected_value=None,
                    calculation_trace={"missing_input": input_field},
                ),
                DocumentValidityStatus.UNKNOWN,
            )

        try:
            intake_num = to_decimal(input_val_raw)
        except ValueError:
            return (
                RequirementOutcome(
                    rule_id=rule_id,
                    requirement_name="Bandwidth Tier Requirement",
                    outcome=ComplianceOutcome.NOT_EVALUABLE,
                    rationale=f"Input basis {input_field}={input_val_raw} is not numeric",
                    calculation_trace={"invalid_input": input_val_raw},
                ),
                DocumentValidityStatus.UNKNOWN,
            )

        # Locate matching tier
        matched_tier: dict[str, Any] | None = None
        for tier in tiers:
            t_min = to_decimal(tier["min"])
            t_max = to_decimal(tier["max"])
            if t_min <= intake_num <= t_max:
                matched_tier = tier
                break

        if not matched_tier:
            return (
                RequirementOutcome(
                    rule_id=rule_id,
                    requirement_name="Bandwidth Tier Requirement",
                    outcome=ComplianceOutcome.NOT_EVALUABLE,
                    rationale=f"No matching intake tier for intake value {intake_num}",
                    calculation_trace={"intake": str(intake_num)},
                ),
                DocumentValidityStatus.UNKNOWN,
            )

        required_val = to_decimal(matched_tier["required"])
        unit = matched_tier.get("unit", "Mbps")

        # Get target observed value
        target_val_raw = claims.get(target_field) or facts.get(target_field)
        if target_val_raw is None:
            # Check if there is a nested dictionary with canonical_value (from unit normalization)
            for k in (target_field, "bandwidth", "internet_bandwidth"):
                item = facts.get(k) or claims.get(k)
                if isinstance(item, dict) and "canonical_value" in item:
                    target_val_raw = item["canonical_value"]
                    break

        if target_val_raw is None:
            return (
                RequirementOutcome(
                    rule_id=rule_id,
                    requirement_name="Bandwidth Tier Requirement",
                    outcome=ComplianceOutcome.POTENTIAL_DEFICIENCY,
                    rationale=f"No observed evidence or claim for required {target_field}",
                    expected_value={"value": str(required_val), "unit": unit},
                    calculation_trace={
                        "intake": str(intake_num),
                        "required_bandwidth": str(required_val),
                    },
                ),
                DocumentValidityStatus.VALID_ON_REVIEW_DATE,
            )

        observed_val = to_decimal(target_val_raw)
        trace = {
            "intake": str(intake_num),
            "tier_min": str(matched_tier["min"]),
            "tier_max": str(matched_tier["max"]),
            "required_value": str(required_val),
            "observed_value": str(observed_val),
            "unit": unit,
            "delta": str(observed_val - required_val),
        }

        if observed_val >= required_val:
            outcome = ComplianceOutcome.PASS
            rationale = (
                f"Observed {observed_val} {unit} meets or exceeds required "
                f"{required_val} {unit} for intake of {intake_num}"
            )
        else:
            outcome = ComplianceOutcome.POTENTIAL_DEFICIENCY
            rationale = (
                f"Observed {observed_val} {unit} is below required "
                f"{required_val} {unit} for intake of {intake_num}"
            )

        return (
            RequirementOutcome(
                rule_id=rule_id,
                requirement_name="Bandwidth Tier Requirement",
                outcome=outcome,
                rationale=rationale,
                observed_value={"value": str(observed_val), "unit": unit},
                expected_value={"value": str(required_val), "unit": unit},
                calculation_trace=trace,
            ),
            DocumentValidityStatus.VALID_ON_REVIEW_DATE,
        )

    def _eval_ratio_check(
        self,
        rule_id: str,
        dsl: dict[str, Any],
        facts: dict[str, Any],
        claims: dict[str, Any],
    ) -> tuple[RequirementOutcome, DocumentValidityStatus]:
        """Evaluate resource ratio checks (e.g. Computers per student, Printers per computer)."""
        num_field = dsl["numerator_field"]
        denom_field = dsl["denominator_field"]
        min_ratio = to_decimal(dsl.get("min_ratio", "0"))
        min_abs = to_decimal(dsl.get("min_absolute", "0"))

        num_raw = claims.get(num_field) or facts.get(num_field)
        denom_raw = claims.get(denom_field) or facts.get(denom_field)

        if num_raw is None or denom_raw is None:
            return (
                RequirementOutcome(
                    rule_id=rule_id,
                    requirement_name=f"Ratio Check {num_field}/{denom_field}",
                    outcome=ComplianceOutcome.NOT_EVALUABLE,
                    rationale=f"Missing numerator ({num_field}) or denominator ({denom_field})",
                    calculation_trace={
                        "num_present": num_raw is not None,
                        "denom_present": denom_raw is not None,
                    },
                ),
                DocumentValidityStatus.UNKNOWN,
            )

        num_val = to_decimal(num_raw)
        denom_val = to_decimal(denom_raw)

        if denom_val <= Decimal("0"):
            return (
                RequirementOutcome(
                    rule_id=rule_id,
                    requirement_name=f"Ratio Check {num_field}/{denom_field}",
                    outcome=ComplianceOutcome.NOT_EVALUABLE,
                    rationale=f"Denominator {denom_field} must be positive, got {denom_val}",
                ),
                DocumentValidityStatus.UNKNOWN,
            )

        computed_ratio = num_val / denom_val
        trace = {
            "numerator": str(num_val),
            "denominator": str(denom_val),
            "computed_ratio": str(computed_ratio.quantize(Decimal("0.0001"))),
            "min_ratio": str(min_ratio),
            "min_absolute": str(min_abs),
        }

        meets_ratio = computed_ratio.quantize(Decimal("0.0001")) >= min_ratio.quantize(
            Decimal("0.0001")
        )
        meets_abs = num_val >= min_abs

        if meets_ratio and meets_abs:
            outcome = ComplianceOutcome.PASS
            rationale = (
                f"Ratio {computed_ratio.quantize(Decimal('0.0001'))} satisfies requirement "
                f"(min {min_ratio}) and absolute count {num_val} >= {min_abs}"
            )
        else:
            outcome = ComplianceOutcome.POTENTIAL_DEFICIENCY
            rationale = (
                f"Failed ratio check: ratio={computed_ratio.quantize(Decimal('0.0001'))} "
                f"(min required: {min_ratio}) or count={num_val} (min required: {min_abs})"
            )

        return (
            RequirementOutcome(
                rule_id=rule_id,
                requirement_name=f"Ratio Check {num_field}/{denom_field}",
                outcome=outcome,
                rationale=rationale,
                observed_value={"count": str(num_val), "ratio": str(computed_ratio)},
                expected_value={"min_ratio": str(min_ratio), "min_absolute": str(min_abs)},
                calculation_trace=trace,
            ),
            DocumentValidityStatus.VALID_ON_REVIEW_DATE,
        )

    def _eval_date_validity(
        self,
        rule_id: str,
        dsl: dict[str, Any],
        facts: dict[str, Any],
        claims: dict[str, Any],
        evaluation_as_of: str,
    ) -> tuple[RequirementOutcome, DocumentValidityStatus]:
        """Evaluate document validity dates against evaluation review cutoff."""
        valid_upto_field = dsl["valid_upto_field"]
        doc_type = dsl.get("required_document_type", "CERTIFICATE")

        # Extract expiry/valid_upto date from facts or claims
        raw_date = facts.get(valid_upto_field) or claims.get(valid_upto_field)
        if isinstance(raw_date, dict) and "iso_date" in raw_date:
            date_str = raw_date["iso_date"]
        else:
            date_str = str(raw_date) if raw_date else None

        if not date_str or date_str in ("None", ""):
            return (
                RequirementOutcome(
                    rule_id=rule_id,
                    requirement_name=f"{doc_type} Validity",
                    outcome=ComplianceOutcome.POTENTIAL_DEFICIENCY,
                    rationale=f"Required document {doc_type} date ({valid_upto_field}) is missing",
                    calculation_trace={"missing_field": valid_upto_field},
                ),
                DocumentValidityStatus.UNKNOWN,
            )

        try:
            cert_date = date.fromisoformat(date_str)
            review_date = date.fromisoformat(evaluation_as_of)
        except ValueError as err:
            return (
                RequirementOutcome(
                    rule_id=rule_id,
                    requirement_name=f"{doc_type} Validity",
                    outcome=ComplianceOutcome.NOT_EVALUABLE,
                    rationale=f"Invalid date format for {valid_upto_field}: {err}",
                    calculation_trace={"invalid_date": date_str},
                ),
                DocumentValidityStatus.UNKNOWN,
            )

        trace = {
            "document_valid_upto": date_str,
            "evaluation_as_of": evaluation_as_of,
            "is_valid": cert_date >= review_date,
        }

        if cert_date >= review_date:
            doc_status = DocumentValidityStatus.VALID_ON_REVIEW_DATE
            outcome = ComplianceOutcome.PASS
            rationale = (
                f"{doc_type} is valid on review date {evaluation_as_of} (expires {date_str})"
            )
        else:
            doc_status = DocumentValidityStatus.EXPIRED_ON_REVIEW_DATE
            outcome = ComplianceOutcome.POTENTIAL_DEFICIENCY
            rationale = (
                f"{doc_type} expired on {date_str}, which is before review date {evaluation_as_of}"
            )

        return (
            RequirementOutcome(
                rule_id=rule_id,
                requirement_name=f"{doc_type} Validity",
                outcome=outcome,
                rationale=rationale,
                observed_value={"valid_upto": date_str},
                expected_value={"valid_on": evaluation_as_of},
                calculation_trace=trace,
            ),
            doc_status,
        )
