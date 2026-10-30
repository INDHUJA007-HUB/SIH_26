"""SIH26262 persistence metadata. Migration 0019 owns database constraints/RLS."""

from sqlalchemy import JSON, Column, DateTime, Integer, String, Table, Text

from workbench.adapters.tables import metadata


def table(name: str, *columns: Column) -> Table:  # type: ignore[type-arg]
    return Table(name, metadata, Column("id", String(36), primary_key=True), *columns)


def s(name: str) -> Column:  # type: ignore[type-arg]
    return Column(name, Text)


def j(name: str) -> Column:  # type: ignore[type-arg]
    return Column(name, JSON)


def dt(name: str) -> Column:  # type: ignore[type-arg]
    return Column(name, DateTime(timezone=True))


packs = table(
    "approval_process_packs",
    s("state"),
    j("content"),
    s("sha256"),
    s("author_id"),
    s("approver_id"),
    dt("created_at"),
    dt("published_at"),
)
grants = table(
    "approval_access_grants",
    s("actor_id"),
    s("role"),
    s("region"),
    s("application_id"),
    s("source_reference"),
    s("granted_by"),
    dt("expires_at"),
    dt("revoked_at"),
)
cases = table(
    "approval_cases",
    s("institution_id"),
    s("application_id"),
    s("region"),
    s("pack_id"),
    s("route"),
    s("stage"),
    s("status"),
    Column("revision", Integer),
    Column("generation", Integer),
    dt("received_at"),
    dt("stage_entered_at"),
    dt("due_at"),
    j("pauses"),
    j("milestones"),
    j("facts"),
)
obligations = table(
    "approval_obligations",
    s("institution_id"),
    s("application_id"),
    s("case_id"),
    s("region"),
    s("pack_id"),
    s("kind"),
    s("code"),
    s("title"),
    s("source_reference"),
    s("state"),
    Column("revision", Integer),
    Column("generation", Integer),
    dt("due_at"),
    s("accepted_evidence_id"),
    s("submitted_evidence_id"),
    dt("submitted_due_at"),
    s("reviewer_id"),
    s("reason"),
    dt("created_at"),
)
rosters = table(
    "evc_rosters",
    s("region"),
    s("source_reference"),
    j("members"),
    j("availability"),
    j("conflicts"),
    s("mode"),
    dt("expires_at"),
)
appointments = table(
    "evc_appointments",
    s("institution_id"),
    s("application_id"),
    s("case_id"),
    s("region"),
    s("roster_id"),
    s("state"),
    j("members"),
    dt("starts_at"),
    dt("ends_at"),
    dt("created_at"),
    s("confirmed_by"),
    j("explanation"),
)
events = table(
    "approval_history",
    s("institution_id"),
    s("application_id"),
    s("case_id"),
    s("resource_id"),
    s("actor_id"),
    s("kind"),
    j("payload"),
    dt("created_at"),
)
alerts = table(
    "approval_deadline_alerts",
    s("institution_id"),
    s("application_id"),
    s("resource_id"),
    s("resource_kind"),
    Column("generation", Integer),
    s("rule_key"),
    s("recipient_role"),
    s("state"),
    dt("trigger_at"),
    dt("created_at"),
)

permits = table(
    "approval_upload_permits",
    s("institution_id"),
    s("application_id"),
    s("obligation_id"),
    s("slot_id"),
    s("authorized_by"),
    s("source_reference"),
    dt("expires_at"),
    dt("revoked_at"),
)
