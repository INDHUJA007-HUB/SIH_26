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
