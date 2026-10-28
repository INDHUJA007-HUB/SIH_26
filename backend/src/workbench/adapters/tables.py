"""PostgreSQL domain metadata; migrations freeze schema changes independently."""

from typing import Any

from sqlalchemy import (
    JSON,
    BigInteger,
    Boolean,
    CheckConstraint,
    Column,
    DateTime,
    Float,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    Integer,
    String,
    Table,
    Text,
    UniqueConstraint,
    func,
)

from workbench.platform.database import Base

metadata = Base.metadata


def pk() -> Column[Any]:
    return Column("id", String(36), primary_key=True)


def institution() -> Column[Any]:
    return Column("institution_id", String(36), ForeignKey("institutions.id"), nullable=False)


def time_created() -> Column[Any]:
    return Column("created_at", DateTime(timezone=True), nullable=False, server_default=func.now())


institutions = Table(
    "institutions",
    metadata,
    pk(),
    Column("name", String(200), nullable=False),
    Column("jurisdiction", String(40), nullable=False),
    Column("synthetic", Boolean, nullable=False),
    time_created(),
)
actors = Table(
    "actor_identities",
    metadata,
    pk(),
    Column("issuer", String(300), nullable=False),
    Column("subject", String(200), nullable=False),
    Column("person_id", String(36), nullable=False),
    Column("disabled", Boolean, nullable=False, server_default="false"),
    Column("valid_after", DateTime(timezone=True), nullable=False),
    time_created(),
    UniqueConstraint("issuer", "subject", name="uq_actor_issuer_subject"),
)
memberships = Table(
    "memberships",
    metadata,
    pk(),
    Column("actor_id", String(36), ForeignKey("actor_identities.id"), nullable=False),
    Column("institution_id", String(36), ForeignKey("institutions.id")),
    Column("role", String(40), nullable=False),
    Column("jurisdiction", String(40)),
    Column("expires_at", DateTime(timezone=True)),
    Column("revoked_at", DateTime(timezone=True)),
    Column("granted_by", String(36)),
    time_created(),
)
sessions = Table(
    "revoked_sessions",
    metadata,
    Column("issuer", String(300), primary_key=True),
    Column("session_id", String(200), primary_key=True),
    time_created(),
)
applications = Table(
    "applications",
    metadata,
    pk(),
    institution(),
    Column("category", String(50), nullable=False),
    Column("cycle_start", Integer, nullable=False),
    Column("programme", String(80), nullable=False),
    Column("level", String(20), nullable=False),
    Column("jurisdiction", String(40), nullable=False),
    Column("portal_system", String(80)),
    Column("portal_reference", String(120)),
    Column("stage", String(30), nullable=False),
    Column("revision", Integer, nullable=False),
    Column("declared_facts", JSON, nullable=False),
    Column("created_by", String(36), nullable=False),
    time_created(),
    UniqueConstraint("institution_id", "id", name="uq_application_owner"),
    UniqueConstraint("portal_system", "portal_reference", name="uq_portal_application"),
    CheckConstraint("cycle_start BETWEEN 2024 AND 2100", name="ck_cycle_start"),
    CheckConstraint("stage IN ('DRAFT','SUBMITTED')", name="ck_intake_stage"),
)
assignments = Table(
    "case_assignments",
    metadata,
    pk(),
    institution(),
    Column("application_id", String(36)),
    Column("actor_id", String(36), ForeignKey("actor_identities.id"), nullable=False),
    Column("access_role", String(20), nullable=False),
    Column("expires_at", DateTime(timezone=True), nullable=False),
    Column("revoked_at", DateTime(timezone=True)),
    Column("granted_by", String(36), nullable=False),
    Column("reason", Text, nullable=False),
    time_created(),
    ForeignKeyConstraint(
        ["institution_id", "application_id"],
        ["applications.institution_id", "applications.id"],
        name="fk_assignment_owner",
    ),
)
case_assignments = assignments
emergency = Table(
    "emergency_grants",
    metadata,
    pk(),
    institution(),
    Column("application_id", String(36), nullable=False),
    Column("requested_by", String(36), ForeignKey("actor_identities.id"), nullable=False),
    Column("approved_by", String(36), ForeignKey("actor_identities.id")),
    Column("reason", Text, nullable=False),
    Column("expires_at", DateTime(timezone=True), nullable=False),
    Column("revoked_at", DateTime(timezone=True)),
    time_created(),
    ForeignKeyConstraint(
        ["institution_id", "application_id"],
        ["applications.institution_id", "applications.id"],
        name="fk_emergency_owner",
    ),
    CheckConstraint("requested_by <> approved_by", name="ck_emergency_distinct_actor"),
)
revisions = Table(
    "application_revisions",
    metadata,
    pk(),
    institution(),
    Column("application_id", String(36), nullable=False),
    Column("revision", Integer, nullable=False),
    Column("stage", String(30), nullable=False),
    Column("manifest", JSON, nullable=False),
    Column("sha256", String(64), nullable=False),
    time_created(),
    UniqueConstraint("application_id", "revision", name="uq_application_revision"),
    ForeignKeyConstraint(
        ["institution_id", "application_id"],
        ["applications.institution_id", "applications.id"],
        name="fk_revision_owner",
    ),
)
slots = Table(
    "evidence_slots",
    metadata,
    pk(),
    institution(),
    Column("application_id", String(36), nullable=False),
    Column("code", String(80), nullable=False),
    Column("required", Boolean, nullable=False),
    time_created(),
    UniqueConstraint("application_id", "code", name="uq_application_slot"),
    UniqueConstraint("institution_id", "application_id", "id", name="uq_slot_owner"),
    ForeignKeyConstraint(
        ["institution_id", "application_id"],
        ["applications.institution_id", "applications.id"],
        name="fk_slot_owner",
    ),
)
uploads = Table(
    "upload_sessions",
    metadata,
    pk(),
    institution(),
    Column("application_id", String(36), nullable=False),
    Column("slot_id", String(36), nullable=False),
    Column("actor_id", String(36), nullable=False),
    Column("filename", String(120), nullable=False),
    Column("media_type", String(100), nullable=False),
    Column("expected_size", BigInteger, nullable=False),
    Column("expected_sha256", String(64), nullable=False),
    Column("object_key", String(250), nullable=False),
    Column("object_version", String(200)),
    Column("mode", String(20), nullable=False),
    Column("multipart_id", String(300)),
    Column("part_size", Integer, nullable=False),
    Column("status", String(30), nullable=False),
    Column("expires_at", DateTime(timezone=True), nullable=False),
    Column("parent_version_id", String(36)),
    time_created(),
    ForeignKeyConstraint(
        ["institution_id", "application_id", "slot_id"],
        ["evidence_slots.institution_id", "evidence_slots.application_id", "evidence_slots.id"],
        name="fk_upload_slot",
    ),
    UniqueConstraint("institution_id", "application_id", "id", name="uq_upload_owner"),
)
evidence = Table(
    "evidence_versions",
    metadata,
    pk(),
    institution(),
    Column("application_id", String(36), nullable=False),
    Column("slot_id", String(36), nullable=False),
    Column("upload_id", String(36), nullable=False, unique=True),
    Column("parent_version_id", String(36)),
    Column("quarantine_key", String(250), nullable=False),
    Column("quarantine_version", String(200), nullable=False),
    Column("size_bytes", BigInteger, nullable=False),
    Column("sha256", String(64), nullable=False),
    Column("media_type", String(100), nullable=False),
    Column("filename", String(120), nullable=False),
    Column("status", String(30), nullable=False),
    Column("reason_code", String(80)),
    Column("clean_key", String(250)),
    Column("clean_version", String(200)),
    Column("metadata", JSON, nullable=False),
    Column("scan_started_at", DateTime(timezone=True)),
    time_created(),
    UniqueConstraint("institution_id", "application_id", "id", name="uq_evidence_owner"),
    ForeignKeyConstraint(
        ["institution_id", "application_id", "slot_id"],
        ["evidence_slots.institution_id", "evidence_slots.application_id", "evidence_slots.id"],
        name="fk_evidence_slot",
    ),
    ForeignKeyConstraint(
        ["institution_id", "application_id", "upload_id"],
        ["upload_sessions.institution_id", "upload_sessions.application_id", "upload_sessions.id"],
        name="fk_evidence_upload",
    ),
    ForeignKeyConstraint(
        ["institution_id", "application_id", "parent_version_id"],
        [
            "evidence_versions.institution_id",
            "evidence_versions.application_id",
            "evidence_versions.id",
        ],
        name="fk_evidence_parent",
    ),
)
derivatives = Table(
    "evidence_derivatives",
    metadata,
    pk(),
    institution(),
    Column("application_id", String(36), nullable=False),
    Column("evidence_id", String(36), nullable=False),
    Column("kind", String(20), nullable=False),
    Column("page", Integer, nullable=False),
    Column("object_key", String(300), nullable=False),
    Column("object_version", String(200), nullable=False),
    Column("sha256", String(64), nullable=False),
    Column("size_bytes", BigInteger, nullable=False),
    Column("media_type", String(80), nullable=False),
    Column("metadata", JSON, nullable=False),
    time_created(),
    UniqueConstraint("evidence_id", "kind", "page", name="uq_derivative_page"),
    ForeignKeyConstraint(
        ["institution_id", "application_id", "evidence_id"],
        [
            "evidence_versions.institution_id",
            "evidence_versions.application_id",
            "evidence_versions.id",
        ],
        name="fk_derivative_owner",
    ),
)
idempotency = Table(
    "command_receipts",
    metadata,
    Column("actor_id", String(36), primary_key=True),
    Column("route", String(100), primary_key=True),
    Column("key", String(128), primary_key=True),
    Column("fingerprint", String(64), nullable=False),
    Column("response", JSON, nullable=False),
    time_created(),
)
audit = Table(
    "audit_events",
    metadata,
    pk(),
    Column("stream", String(80), nullable=False),
    Column("institution_id", String(36)),
    Column("application_id", String(36)),
    Column("sequence", BigInteger, nullable=False),
    Column("previous_hash", String(64), nullable=False),
    Column("sha256", String(64), nullable=False),
    Column("event", JSON, nullable=False),
    time_created(),
    UniqueConstraint("stream", "sequence", name="uq_audit_sequence"),
)
access = Table(
    "access_events",
    metadata,
    pk(),
    Column("actor_id", String(36)),
    Column("institution_id", String(36)),
    Column("application_id", String(36)),
    Column("evidence_id", String(36)),
    Column("resource_id", String(100), nullable=False),
    Column("action", String(30), nullable=False),
    Column("result", String(30), nullable=False),
    Column("bytes_served", BigInteger, nullable=False),
    Column("request_id", String(64), nullable=False),
    Column("parent_event_id", String(36)),
    time_created(),
)
outbox = Table(
    "outbox_events",
    metadata,
    pk(),
    institution(),
    Column("application_id", String(36), nullable=False),
    Column("event_type", String(80), nullable=False),
    Column("payload", JSON, nullable=False),
    Column("lease_owner", String(36)),
    Column("lease_until", DateTime(timezone=True)),
    Column("attempts", Integer, nullable=False, server_default="0"),
    Column("available_at", DateTime(timezone=True), nullable=False, server_default=func.now()),
    Column("delivered_at", DateTime(timezone=True)),
    time_created(),
    ForeignKeyConstraint(
        ["institution_id", "application_id"],
        ["applications.institution_id", "applications.id"],
        name="fk_outbox_owner",
    ),
)
receipts = Table(
    "consumer_receipts",
    metadata,
    Column("event_id", String(36), ForeignKey("outbox_events.id"), primary_key=True),
    time_created(),
)
tasks = Table(
    "operations_tasks",
    metadata,
    pk(),
    Column("institution_id", String(36)),
    Column("application_id", String(36)),
    Column("kind", String(60), nullable=False),
    Column("resource_id", String(300), nullable=False),
    Column("state", String(20), nullable=False),
    Column("details", JSON, nullable=False),
    time_created(),
    UniqueConstraint("kind", "resource_id", name="uq_operation_condition"),
)

operations = Table(
    "operations",
    metadata,
    pk(),
    institution(),
    Column("application_id", String(36)),
    Column("operation_type", String(80), nullable=False),
    Column("task_queue", String(60), nullable=False),
    Column("status", String(30), nullable=False),
    Column("stable_key", String(200), nullable=False),
    Column("workflow_id", String(120)),
    Column("input_ref", JSON, nullable=False),
    Column("result", JSON),
    Column("error_code", String(80)),
    Column("error_message", Text),
    Column("attempts", Integer, nullable=False, server_default="0"),
    Column("paused", Boolean, nullable=False, server_default="false"),
    time_created(),
    Column("updated_at", DateTime(timezone=True), nullable=False, server_default=func.now()),
    UniqueConstraint(
        "institution_id", "operation_type", "stable_key", name="uq_operation_stable_key"
    ),
    ForeignKeyConstraint(
        ["institution_id", "application_id"],
        ["applications.institution_id", "applications.id"],
        name="fk_operation_owner",
    ),
)

reconciliation_cursors = Table(
    "reconciliation_cursors",
    metadata,
    Column("name", String(40), primary_key=True),
    Column("position", JSON, nullable=False),
)

extraction_runs = Table(
    "extraction_runs",
    metadata,
    pk(),
    institution(),
    Column("application_id", String(36)),
    Column("evidence_version_id", String(36), ForeignKey("evidence_versions.id"), nullable=False),
    Column("extractor_version", String(80), nullable=False),
    Column("document_type", String(80), nullable=False),
    Column("page_count", Integer, nullable=False, server_default="1"),
    Column("status", String(30), nullable=False),
    Column("metadata", JSON),
    time_created(),
    Column("updated_at", DateTime(timezone=True), nullable=False, server_default=func.now()),
)

extracted_fields = Table(
    "extracted_fields",
    metadata,
    pk(),
    Column("run_id", String(36), ForeignKey("extraction_runs.id"), nullable=False),
    institution(),
    Column("application_id", String(36)),
    Column("evidence_version_id", String(36), ForeignKey("evidence_versions.id"), nullable=False),
    Column("field_name", String(100), nullable=False),
    Column("field_type", String(50), nullable=False),
    Column("raw_value", Text),
    Column("normalized_value", JSON),
    Column("page_number", Integer, nullable=False, server_default="1"),
    Column("bounding_box", JSON),
    Column("rotation", Integer, nullable=False, server_default="0"),
    Column("confidence", Float, nullable=False, server_default="1.0"),
    Column("uncertainty", String(50), nullable=False, server_default="LOW"),
    Column("method", String(50), nullable=False, server_default="DIGITAL_TEXT"),
    Column("is_current", Boolean, nullable=False, server_default="true"),
    time_created(),
)

field_corrections = Table(
    "field_corrections",
    metadata,
    pk(),
    institution(),
    Column("application_id", String(36)),
    Column("field_id", String(36), ForeignKey("extracted_fields.id"), nullable=False),
    Column("prior_value", JSON),
    Column("corrected_value", JSON, nullable=False),
    Column("reason", Text, nullable=False),
    Column("corrected_by", String(36), nullable=False),
    Column("authority", String(80), nullable=False),
    time_created(),
)

fact_sets = Table(
    "fact_sets",
    metadata,
    pk(),
    institution(),
    Column("application_id", String(36), ForeignKey("applications.id"), nullable=False),
    Column("version", Integer, nullable=False, server_default="1"),
    Column("canonical_hash", String(64), nullable=False),
    Column(
        "canonicalization_version",
        String(40),
        nullable=False,
        server_default="jcs-and-project-types-v1",
    ),
    Column("is_frozen", Boolean, nullable=False, server_default="true"),
    time_created(),
    UniqueConstraint("application_id", "version", name="uq_fact_set_application_version"),
)

fact_set_members = Table(
    "fact_set_members",
    metadata,
    pk(),
    Column("fact_set_id", String(36), ForeignKey("fact_sets.id"), nullable=False),
    institution(),
    Column("application_id", String(36), nullable=False),
    Column("field_id", String(36), ForeignKey("extracted_fields.id"), nullable=False),
    Column("field_name", String(100), nullable=False),
    Column("normalized_value", JSON, nullable=False),
    time_created(),
)

claims = Table(
    "claims",
    metadata,
    pk(),
    institution(),
    Column("application_id", String(36), ForeignKey("applications.id"), nullable=False),
    Column("subject", String(120), nullable=False),
    Column("predicate", String(100), nullable=False),
    Column("period_start", String(40)),
    Column("period_end", String(40)),
    Column("declared_value", JSON),
    Column("reconciled_value", JSON),
    Column("status", String(40), nullable=False, server_default="UNVERIFIED"),
    time_created(),
    Column("updated_at", DateTime(timezone=True), nullable=False, server_default=func.now()),
)

claim_evidence_links = Table(
    "claim_evidence_links",
    metadata,
    pk(),
    Column("claim_id", String(36), ForeignKey("claims.id"), nullable=False),
    institution(),
    Column("application_id", String(36), nullable=False),
    Column("evidence_version_id", String(36), ForeignKey("evidence_versions.id"), nullable=False),
    Column("field_id", String(36)),
    Column("relationship", String(30), nullable=False, server_default="SUPPORTS"),
    Column("rationale", Text),
    time_created(),
)

rule_sources = Table(
    "rule_sources",
    metadata,
    pk(),
    Column("source_code", String(50), nullable=False, unique=True),
    Column("title", String(200), nullable=False),
    Column("sha256", String(64), nullable=False),
    Column("bytes_size", BigInteger),
    Column("status", String(80), nullable=False),
    Column("publisher_reference", String(500)),
    Column("pdf_pages", Integer),
    Column("checked_on", String(40)),
    time_created(),
)

rule_interpretations = Table(
    "rule_interpretations",
    metadata,
    pk(),
    Column("rule_id", String(100), nullable=False, unique=True),
    Column("clause", String(100)),
    Column("source_id", String(36)),
    Column(
        "interpretation_state",
        String(50),
        nullable=False,
        server_default="REQUIRES_AUTHORIZED_REVIEW",
    ),
    Column("content_status", String(50), nullable=False, server_default="V-U"),
    Column("summary", JSON),
    Column("notes", Text),
    time_created(),
    Column("updated_at", DateTime(timezone=True), nullable=False, server_default=func.now()),
)

rule_versions = Table(
    "rule_versions",
    metadata,
    pk(),
    Column("rule_id", String(100), nullable=False),
    Column("version", Integer, nullable=False, server_default="1"),
    Column("content_hash", String(64), nullable=False),
    Column("source_id", String(36)),
    Column("clause", String(100)),
    Column("printed_page", Integer),
    Column("pdf_page", Integer),
    Column("page_offset", Integer, nullable=False, server_default="16"),
    Column("applicability", JSON),
    Column("parameters", JSON),
    Column("dsl_expression", JSON),
    Column("status", String(50), nullable=False, server_default="DRAFT"),
    Column("production_enabled", Boolean, nullable=False, server_default="false"),
    Column("adverse_action_allowed", Boolean, nullable=False, server_default="false"),
    time_created(),
    UniqueConstraint("rule_id", "version", name="uq_rule_version_rule_ver"),
)

rule_releases = Table(
    "rule_releases",
    metadata,
    pk(),
    Column("release_code", String(50), nullable=False, unique=True),
    Column("version", Integer, nullable=False, server_default="1"),
    Column("academic_cycle", String(50), nullable=False),
    Column("content_hash", String(64), nullable=False),
    Column("status", String(50), nullable=False, server_default="DRAFT"),
    Column("approved_by", String(36)),
    Column("is_active", Boolean, nullable=False, server_default="false"),
    time_created(),
)

release_members = Table(
    "release_members",
    metadata,
    pk(),
    Column("release_id", String(36), ForeignKey("rule_releases.id"), nullable=False),
    Column("rule_version_id", String(36), ForeignKey("rule_versions.id"), nullable=False),
    Column("rule_id", String(100), nullable=False),
    time_created(),
    UniqueConstraint("release_id", "rule_id", name="uq_release_rule"),
)

evaluation_runs = Table(
    "evaluation_runs",
    metadata,
    pk(),
    institution(),
    Column("application_id", String(36), ForeignKey("applications.id"), nullable=False),
    Column("application_revision_id", String(36)),
    Column("rule_release_id", String(36)),
    Column("fact_set_id", String(36)),
    Column("manifest_hash", String(64), nullable=False),
    Column("evaluation_as_of", String(40), nullable=False),
    Column("execution_mode", String(40), nullable=False, server_default="DEMONSTRATION"),
    Column("completeness_status", String(40), nullable=False, server_default="COMPLETE"),
    Column("compliance_status", String(40), nullable=False, server_default="PASS"),
    Column(
        "source_verification_status",
        String(40),
        nullable=False,
        server_default="VERIFICATION_PENDING",
    ),
    Column(
        "forensic_concern_status",
        String(40),
        nullable=False,
        server_default="NONE_OBSERVED",
    ),
    Column(
        "document_validity_status",
        String(40),
        nullable=False,
        server_default="VALID_ON_REVIEW_DATE",
    ),
    Column("case_workflow_status", String(40), nullable=False, server_default="SCREENED"),
    Column("adverse_action_allowed", Boolean, nullable=False, server_default="false"),
    Column("manifest", JSON),
    time_created(),
)

run_inputs = Table(
    "run_inputs",
    metadata,
    pk(),
    Column("run_id", String(36), ForeignKey("evaluation_runs.id"), nullable=False),
    institution(),
    Column("application_id", String(36), nullable=False),
    Column("input_type", String(50), nullable=False),
    Column("input_id", String(36), nullable=False),
    Column("content_hash", String(64), nullable=False),
    time_created(),
)

requirement_outcomes = Table(
    "requirement_outcomes",
    metadata,
    pk(),
    Column("run_id", String(36), ForeignKey("evaluation_runs.id"), nullable=False),
    institution(),
    Column("application_id", String(36), nullable=False),
    Column("rule_id", String(100), nullable=False),
    Column("requirement_name", String(150), nullable=False),
    Column("outcome", String(40), nullable=False, server_default="PASS"),
    Column("rationale", Text),
    Column("observed_value", JSON),
    Column("expected_value", JSON),
    Column("calculation_trace", JSON),
    time_created(),
)

findings = Table(
    "findings",
    metadata,
    pk(),
    Column("run_id", String(36), ForeignKey("evaluation_runs.id"), nullable=False),
    institution(),
    Column("application_id", String(36), nullable=False),
    Column("rule_id", String(100), nullable=False),
    Column("semantic_key", String(150), nullable=False),
    Column("dimension", String(40), nullable=False, server_default="COMPLIANCE"),
    Column("severity", String(40), nullable=False, server_default="DEFICIENCY"),
    Column("status", String(40), nullable=False, server_default="OPEN"),
    Column("title", String(250), nullable=False),
    Column("description", Text),
    Column("officer_explanation", Text),
    Column("applicant_explanation", Text),
    Column("calculation_trace", JSON),
    Column("supporting_evidence", JSON),
    Column("contradicting_evidence", JSON),
    Column("unknown_reason", Text),
    Column("adverse_action_allowed", Boolean, nullable=False, server_default="false"),
    time_created(),
)

historical_records = Table(
    "historical_records",
    metadata,
    pk(),
    institution(),
    Column("source", String(50), nullable=False),
    Column("record_type", String(50), nullable=False),
    Column("academic_cycle", Integer, nullable=False),
    Column("payload", JSON, nullable=False),
    Column("payload_sha256", String(64), nullable=False),
    Column("external_reference", String(200), nullable=False),
    Column("valid_from", DateTime(timezone=True), nullable=False),
    Column("valid_to", DateTime(timezone=True)),
    Column("simulated", Boolean, nullable=False, server_default="true"),
    Column("import_lineage", JSON),
    time_created(),
)

source_observations = Table(
    "source_observations",
    metadata,
    pk(),
    institution(),
    Column("evidence_id", String(36)),
    Column("evidence_version_id", String(36)),
    Column("claim_id", String(36)),
    Column("provider_code", String(50), nullable=False),
    Column("mode", String(20), nullable=False, server_default="SIMULATED"),
    Column("simulated", Boolean, nullable=False, server_default="true"),
    Column("live_success", Boolean, nullable=False, server_default="false"),
    Column("status", String(50), nullable=False),
    Column("observed_value", JSON),
    Column("discrepancy_details", JSON),
    Column("freshness_timestamp", DateTime(timezone=True), nullable=False),
    Column("observation_fingerprint", String(64), nullable=False),
    time_created(),
)

verification_attempts = Table(
    "verification_attempts",
    metadata,
    pk(),
    institution(),
    Column("evidence_id", String(36), nullable=False),
    Column("evidence_version_id", String(36), nullable=False),
    Column("claim_id", String(36)),
    Column("provider_code", String(50), nullable=False),
    Column("attempt_number", Integer, nullable=False, server_default="1"),
    Column("status", String(50), nullable=False),
    Column("error_code", String(50)),
    Column("error_message", Text),
    Column("request_fingerprint", String(64), nullable=False),
    Column("simulated", Boolean, nullable=False, server_default="true"),
    Column("outage_escalated_to_task", Boolean, nullable=False, server_default="false"),
    Column("manual_task_id", String(36)),
    time_created(),
)

signature_validations = Table(
    "signature_validations",
    metadata,
    pk(),
    institution(),
    Column("evidence_id", String(36), nullable=False),
    Column("evidence_version_id", String(36), nullable=False),
    Column("validation_type", String(50), nullable=False),
    Column("status", String(50), nullable=False),
    Column("signer_identity", String(200)),
    Column("signer_role", String(50), nullable=False, server_default="UNKNOWN"),
    Column("signing_time", DateTime(timezone=True)),
    Column("certificate_sha256", String(64)),
    Column("qr_payload", JSON),
    Column("qr_target_url", String(1000)),
    Column("destination_safe", Boolean, nullable=False, server_default="true"),
    Column("simulated", Boolean, nullable=False, server_default="true"),
    Column("details", JSON),
    time_created(),
)

# Phase 9: Review, reports, response windows, and rectification
review_dispositions = Table(
    "review_dispositions",
    metadata,
    pk(),
    institution(),
    Column("application_id", String(36), ForeignKey("applications.id"), nullable=False),
    Column("finding_id", String(36), nullable=False),
    Column("evaluation_run_id", String(36), nullable=False),
    Column("officer_id", String(36), ForeignKey("actor_identities.id"), nullable=False),
    Column("disposition", String(50), nullable=False),
    Column("rationale", Text, nullable=False),
    Column("metadata", JSON),
    time_created(),
    Column("updated_at", DateTime(timezone=True), nullable=False, server_default=func.now()),
)

review_tasks = Table(
    "review_tasks",
    metadata,
    pk(),
    institution(),
    Column("application_id", String(36), ForeignKey("applications.id"), nullable=False),
    Column("task_type", String(50), nullable=False),
    Column("waiting_on", String(50), nullable=False),
    Column("status", String(50), nullable=False, server_default="PENDING"),
    Column("assigned_to", String(36)),
    Column("details", JSON),
    Column("deadline", DateTime(timezone=True)),
    time_created(),
    Column("resolved_at", DateTime(timezone=True)),
)

validation_reports = Table(
    "validation_reports",
    metadata,
    pk(),
    institution(),
    Column("application_id", String(36), ForeignKey("applications.id"), nullable=False),
    Column("evaluation_run_id", String(36), nullable=False),
    Column("audience", String(20), nullable=False),
    Column("version", Integer, nullable=False, server_default="1"),
    Column("report_hash", String(64), nullable=False),
    Column("status", String(20), nullable=False, server_default="FINAL"),
    Column("summary", JSON, nullable=False),
    Column("content", JSON, nullable=False),
    Column("disclosure_policy", JSON, nullable=False),
    time_created(),
    UniqueConstraint(
        "application_id",
        "audience",
        "version",
        name="uq_validation_report_app_audience_ver",
    ),
)

response_windows = Table(
    "response_windows",
    metadata,
    pk(),
    institution(),
    Column("application_id", String(36), ForeignKey("applications.id"), nullable=False),
    Column("opened_by", String(36), nullable=False),
    Column("authority_reference", String(100), nullable=False),
    Column("round_number", Integer, nullable=False, server_default="1"),
    Column("max_rounds", Integer, nullable=False, server_default="2"),
    Column("allowed_slots", JSON, nullable=False),
    Column("allowed_fields", JSON, nullable=False),
    Column("deadline", DateTime(timezone=True), nullable=False),
    Column("status", String(30), nullable=False, server_default="OPEN"),
    Column("current_revision", Integer, nullable=False),
    time_created(),
    Column("closed_at", DateTime(timezone=True)),
)

rectification_responses = Table(
    "rectification_responses",
    metadata,
    pk(),
    Column("window_id", String(36), ForeignKey("response_windows.id"), nullable=False),
    institution(),
    Column("application_id", String(36), ForeignKey("applications.id"), nullable=False),
    Column("submitted_by", String(36), nullable=False),
    Column("application_revision", Integer, nullable=False),
    Column("response_manifest", JSON, nullable=False),
    Column("declared_field_updates", JSON),
    Column("reassessment_run_id", String(36)),
    time_created(),
)

reassessment_diffs = Table(
    "reassessment_diffs",
    metadata,
    pk(),
    institution(),
    Column("application_id", String(36), ForeignKey("applications.id"), nullable=False),
    Column("response_id", String(36)),
    Column("baseline_run_id", String(36), nullable=False),
    Column("reassessment_run_id", String(36), nullable=False),
    Column("diff_summary", JSON, nullable=False),
    Column("finding_diffs", JSON, nullable=False),
    time_created(),
)

# Phase 10: Alerts, semantic lifecycle tasks, durable timers, notifications, and audit checkpoints
alerts = Table(
    "alerts",
    metadata,
    pk(),
    institution(),
    Column("application_id", String(36), ForeignKey("applications.id")),
    Column("category", String(50), nullable=False),
    Column("trigger_type", String(50), nullable=False),
    Column("dedup_key", String(255), nullable=False),
    Column("severity", String(20), nullable=False),
    Column("title", String(200), nullable=False),
    Column("message", Text, nullable=False),
    Column("status", String(30), nullable=False, server_default="OPEN"),
    Column("details", JSON),
    time_created(),
    Column("acknowledged_at", DateTime(timezone=True)),
    Column("resolved_at", DateTime(timezone=True)),
    Column("acknowledged_by", String(36)),
)

lifecycle_tasks = Table(
    "lifecycle_tasks",
    metadata,
    pk(),
    institution(),
    Column("application_id", String(36), ForeignKey("applications.id")),
    Column("task_type", String(50), nullable=False),
    Column("dedup_key", String(255), nullable=False),
    Column("state", String(30), nullable=False, server_default="OPEN"),
    Column("assigned_to", String(36)),
    Column("details", JSON),
    time_created(),
    Column("updated_at", DateTime(timezone=True), nullable=False, server_default=func.now()),
    Column("resolved_at", DateTime(timezone=True)),
)

durable_timers = Table(
    "durable_timers",
    metadata,
    pk(),
    institution(),
    Column("application_id", String(36), ForeignKey("applications.id"), nullable=False),
    Column("slot_id", String(36)),
    Column("timer_type", String(50), nullable=False),
    Column("generation", Integer, nullable=False, server_default="1"),
    Column("deadline", DateTime(timezone=True), nullable=False),
    Column("status", String(30), nullable=False, server_default="SCHEDULED"),
    Column("details", JSON),
    time_created(),
    Column("cancelled_at", DateTime(timezone=True)),
    Column("fired_at", DateTime(timezone=True)),
)

notifications = Table(
    "notifications",
    metadata,
    pk(),
    institution(),
    Column("application_id", String(36), ForeignKey("applications.id")),
    Column("alert_id", String(36), ForeignKey("alerts.id")),
    Column("task_id", String(36), ForeignKey("lifecycle_tasks.id")),
    Column("recipient", String(255), nullable=False),
    Column("channel", String(20), nullable=False),
    Column("status", String(30), nullable=False, server_default="QUEUED"),
    Column("provider_reference", String(100)),
    Column("subject", String(250)),
    Column("body", Text, nullable=False),
    Column("retry_count", Integer, nullable=False, server_default="0"),
    Column("retry_history", JSON),
    time_created(),
    Column("sent_at", DateTime(timezone=True)),
    Column("acknowledged_at", DateTime(timezone=True)),
)

audit_checkpoints = Table(
    "audit_checkpoints",
    metadata,
    pk(),
    institution(),
    Column("application_id", String(36), ForeignKey("applications.id")),
    Column("auditor_id", String(36), ForeignKey("actor_identities.id"), nullable=False),
    Column("stream", String(80), nullable=False),
    Column("start_sequence", BigInteger, nullable=False),
    Column("end_sequence", BigInteger, nullable=False),
    Column("event_count", Integer, nullable=False),
    Column("checkpoint_hash", String(64), nullable=False),
    Column("archive_lag_seconds", Float, nullable=False, server_default="0"),
    Column("integrity_status", String(20), nullable=False, server_default="VERIFIED"),
    Column("manifest", JSON, nullable=False),
    time_created(),
)

# Phase 11: Media evidence, frame sampling, equipment detection, and floor plan reconciliation
media_metadata = Table(
    "media_metadata",
    metadata,
    pk(),
    institution(),
    Column("evidence_id", String(36), nullable=False),
    Column("evidence_version_id", String(36), ForeignKey("evidence_versions.id"), nullable=False),
    Column("media_type", String(50), nullable=False),
    Column("video_role", String(50), nullable=False, server_default="NONE"),
    Column("duration_seconds", Float, nullable=False, server_default="0"),
    Column("dimensions", JSON),
    Column("codec", String(50)),
    Column("frame_rate", Float),
    Column("bitrate_kbps", Integer),
    Column("gps_metadata", JSON),
    Column("has_gps", Boolean, nullable=False, server_default="false"),
    Column("metadata_status", String(50), nullable=False, server_default="VALID"),
    Column("duration_policy_result", JSON),
    Column("exif_raw", JSON),
    time_created(),
)

media_sampled_frames = Table(
    "media_sampled_frames",
    metadata,
    pk(),
    institution(),
    Column("media_metadata_id", String(36), ForeignKey("media_metadata.id"), nullable=False),
    Column("evidence_version_id", String(36), ForeignKey("evidence_versions.id"), nullable=False),
    Column("frame_index", Integer, nullable=False),
    Column("timestamp_seconds", Float, nullable=False),
    Column("perceptual_hash", String(64), nullable=False),
    Column("difference_hash", String(64)),
    Column("average_hash", String(64)),
    Column("frame_storage_key", String(255)),
    Column("is_keyframe", Boolean, nullable=False, server_default="true"),
    time_created(),
)

media_similarity_matches = Table(
    "media_similarity_matches",
    metadata,
    pk(),
    institution(),
    Column(
        "source_evidence_version_id",
        String(36),
        ForeignKey("evidence_versions.id"),
        nullable=False,
    ),
    Column(
        "target_evidence_version_id",
        String(36),
        ForeignKey("evidence_versions.id"),
        nullable=False,
    ),
    Column("source_frame_id", String(36), ForeignKey("media_sampled_frames.id")),
    Column("target_frame_id", String(36), ForeignKey("media_sampled_frames.id")),
    Column("similarity_score", Float, nullable=False),
    Column("hamming_distance", Integer, nullable=False),
    Column("match_type", String(50), nullable=False),
    Column("scope", String(50), nullable=False, server_default="INTRA_APPLICATION"),
    Column(
        "advisory_disposition",
        String(50),
        nullable=False,
        server_default="POTENTIAL_REPEATED_SCENE",
    ),
    time_created(),
)

equipment_detections = Table(
    "equipment_detections",
    metadata,
    pk(),
    institution(),
    Column("application_id", String(36), ForeignKey("applications.id"), nullable=False),
    Column("evidence_version_id", String(36), ForeignKey("evidence_versions.id"), nullable=False),
    Column("room_identifier", String(100), nullable=False),
    Column("equipment_category", String(50), nullable=False, server_default="WORKSTATION"),
    Column("declared_quantity", Integer, nullable=False),
    Column("model_mode", String(50), nullable=False, server_default="INFERENCE_RUN"),
    Column("model_name", String(100), nullable=False),
    Column("model_version", String(50), nullable=False),
    Column("detected_candidate_count", Integer, nullable=False),
    Column("detected_boxes", JSON, nullable=False),
    Column("confidence_score", Float, nullable=False, server_default="0.85"),
    Column("coverage_assessment", JSON, nullable=False),
    Column("advisory_finding", Text, nullable=False),
    Column("human_correction", JSON),
    Column("status", String(50), nullable=False, server_default="ADVISORY_PENDING_REVIEW"),
    time_created(),
)

floor_plan_reconciliations = Table(
    "floor_plan_reconciliations",
    metadata,
    pk(),
    institution(),
    Column("application_id", String(36), ForeignKey("applications.id"), nullable=False),
    Column("evidence_version_id", String(36), ForeignKey("evidence_versions.id"), nullable=False),
    Column("plan_name", String(100), nullable=False),
    Column("total_declared_area_sqm", Float, nullable=False),
    Column("total_measured_area_sqm", Float, nullable=False),
    Column("declared_spaces", JSON, nullable=False),
    Column("identified_spaces", JSON, nullable=False),
    Column("matched_spaces", JSON, nullable=False),
    Column("discrepancies", JSON, nullable=False),
    Column("reconciliation_status", String(50), nullable=False, server_default="RECONCILED"),
    Column("notes", Text),
    time_created(),
)

for table in (
    applications,
    assignments,
    revisions,
    slots,
    uploads,
    evidence,
    derivatives,
    outbox,
    operations,
    extraction_runs,
    extracted_fields,
    field_corrections,
    fact_sets,
    fact_set_members,
    claims,
    claim_evidence_links,
    evaluation_runs,
    run_inputs,
    requirement_outcomes,
    findings,
    historical_records,
    source_observations,
    verification_attempts,
    signature_validations,
    review_dispositions,
    review_tasks,
    validation_reports,
    response_windows,
    rectification_responses,
    reassessment_diffs,
    alerts,
    lifecycle_tasks,
    durable_timers,
    notifications,
    audit_checkpoints,
    media_metadata,
    media_sampled_frames,
    media_similarity_matches,
    equipment_detections,
    floor_plan_reconciliations,
):
    Index(f"ix_{table.name}_owner_time", table.c.institution_id, table.c.created_at, table.c.id)
Index("ix_outbox_delivery", outbox.c.delivered_at, outbox.c.available_at, outbox.c.lease_until)
Index("ix_evidence_clean_object", evidence.c.clean_key, evidence.c.clean_version)
Index("ix_derivative_object", derivatives.c.object_key, derivatives.c.object_version)
Index("ix_operations_institution_status", operations.c.institution_id, operations.c.status)
Index("ix_operations_status_queue", operations.c.status, operations.c.task_queue)
Index(
    "ix_extraction_runs_evidence", extraction_runs.c.evidence_version_id, extraction_runs.c.status
)
Index("ix_extracted_fields_run", extracted_fields.c.run_id, extracted_fields.c.field_name)
Index(
    "ix_extracted_fields_evidence",
    extracted_fields.c.evidence_version_id,
    extracted_fields.c.field_name,
)
Index("ix_fact_sets_application", fact_sets.c.application_id, fact_sets.c.version)
Index("ix_claims_application", claims.c.application_id, claims.c.subject, claims.c.predicate)
Index("ix_claim_evidence_links_claim", claim_evidence_links.c.claim_id)
Index("ix_rule_sources_code", rule_sources.c.source_code)
Index("ix_rule_interpretations_rule", rule_interpretations.c.rule_id)
Index("ix_rule_versions_rule_ver", rule_versions.c.rule_id, rule_versions.c.version)
Index("ix_rule_releases_code", rule_releases.c.release_code)
Index("ix_release_members_release", release_members.c.release_id)
Index(
    "ix_evaluation_runs_app",
    evaluation_runs.c.application_id,
    evaluation_runs.c.institution_id,
)
Index("ix_run_inputs_run", run_inputs.c.run_id)
Index("ix_req_outcomes_run", requirement_outcomes.c.run_id, requirement_outcomes.c.rule_id)
Index("ix_findings_run_semantic", findings.c.run_id, findings.c.semantic_key)
Index(
    "ix_historical_records_cycle",
    historical_records.c.institution_id,
    historical_records.c.academic_cycle,
    historical_records.c.record_type,
)
Index("ix_source_observations_claim", source_observations.c.claim_id)
Index("ix_source_observations_evidence", source_observations.c.evidence_version_id)
Index("ix_verification_attempts_req", verification_attempts.c.request_fingerprint)
Index("ix_signature_validations_evidence", signature_validations.c.evidence_version_id)
Index("ix_review_dispositions_finding", review_dispositions.c.finding_id)
Index("ix_review_tasks_status", review_tasks.c.status, review_tasks.c.waiting_on)
Index(
    "ix_validation_reports_run",
    validation_reports.c.evaluation_run_id,
    validation_reports.c.audience,
    validation_reports.c.version,
)
Index("ix_response_windows_app", response_windows.c.application_id, response_windows.c.status)
Index("ix_rectification_responses_window", rectification_responses.c.window_id)
Index(
    "ix_reassessment_diffs_runs",
    reassessment_diffs.c.baseline_run_id,
    reassessment_diffs.c.reassessment_run_id,
)
Index("ix_alerts_dedup_status", alerts.c.dedup_key, alerts.c.status)
Index("ix_alerts_category_status", alerts.c.category, alerts.c.status)
Index("ix_lifecycle_tasks_dedup", lifecycle_tasks.c.dedup_key)
Index("ix_durable_timers_slot_gen", durable_timers.c.slot_id, durable_timers.c.generation)
Index("ix_notifications_status", notifications.c.status)
Index("ix_audit_checkpoints_app", audit_checkpoints.c.application_id)
Index(
    "ix_media_metadata_evidence",
    media_metadata.c.evidence_id,
    media_metadata.c.evidence_version_id,
)
Index(
    "ix_sampled_frames_meta",
    media_sampled_frames.c.media_metadata_id,
    media_sampled_frames.c.frame_index,
)
Index("ix_sampled_frames_phash", media_sampled_frames.c.perceptual_hash)
Index(
    "ix_similarity_matches_source",
    media_similarity_matches.c.source_evidence_version_id,
)
Index(
    "ix_similarity_matches_target",
    media_similarity_matches.c.target_evidence_version_id,
)
Index(
    "ix_equipment_detections_app_room",
    equipment_detections.c.application_id,
    equipment_detections.c.room_identifier,
)
Index("ix_floor_plan_reconciliations_app", floor_plan_reconciliations.c.application_id)
