"""Database adapter for rule registry sources, interpretations, releases, and members."""

from __future__ import annotations

import uuid

from sqlalchemy import Connection, Engine, select
from sqlalchemy.dialects.postgresql import insert

from workbench.adapters import tables as t
from workbench.modules.rule_registry.importer import RuleRegistryImporter
from workbench.modules.rule_registry.models import (
    PublicationState,
    RuleReleaseRecord,
    RuleVersionRecord,
)


class RuleRegistryService:
    """Manages persistence and retrieval of rule sources, versions, and active releases."""

    def __init__(self, engine: Engine) -> None:
        self.engine = engine
        self.importer = RuleRegistryImporter()

    def seed_default_rules(self, conn: Connection | None = None) -> RuleReleaseRecord:
        """Seed all 22 rule records, interpretations, versions, and the active seed release."""
        if conn is not None:
            return self._seed_with_conn(conn)
        with self.engine.begin() as connection:
            return self._seed_with_conn(connection)

    def _seed_with_conn(self, conn: Connection) -> RuleReleaseRecord:
        sources = self.importer.load_sources()
        for src in sources:
            stmt = (
                insert(t.rule_sources)
                .values(
                    id=src.id,
                    source_code=src.source_code,
                    title=src.title,
                    sha256=src.sha256,
                    bytes_size=src.bytes_size,
                    status=src.status,
                    publisher_reference=src.publisher_reference,
                    pdf_pages=src.pdf_pages,
                    checked_on=src.checked_on,
                )
                .on_conflict_do_nothing(index_elements=["source_code"])
            )
            conn.execute(stmt)

        interpretations, versions, release = self.importer.load_rules_and_versions()

        for interp in interpretations:
            stmt = (
                insert(t.rule_interpretations)
                .values(
                    id=interp.id,
                    rule_id=interp.rule_id,
                    clause=interp.clause,
                    source_id=interp.source_id,
                    interpretation_state=interp.interpretation_state.value,
                    content_status=interp.content_status,
                    summary=interp.summary,
                    notes=interp.notes,
                )
                .on_conflict_do_nothing(index_elements=["rule_id"])
            )
            conn.execute(stmt)

        for ver in versions:
            stmt = (
                insert(t.rule_versions)
                .values(
                    id=ver.id,
                    rule_id=ver.rule_id,
                    version=ver.version,
                    content_hash=ver.content_hash,
                    source_id=ver.source_id,
                    clause=ver.clause,
                    printed_page=ver.printed_page,
                    pdf_page=ver.pdf_page,
                    page_offset=ver.page_offset,
                    applicability=ver.applicability,
                    parameters=ver.parameters,
                    dsl_expression=ver.dsl_expression,
                    status=ver.status.value,
                    production_enabled=ver.production_enabled,
                    adverse_action_allowed=ver.adverse_action_allowed,
                )
                .on_conflict_do_nothing(index_elements=["rule_id", "version"])
            )
            conn.execute(stmt)

        stmt = (
            insert(t.rule_releases)
            .values(
                id=release.id,
                release_code=release.release_code,
                version=release.version,
                academic_cycle=release.academic_cycle,
                content_hash=release.content_hash,
                status=release.status.value,
                approved_by=release.approved_by,
                is_active=True,
            )
            .on_conflict_do_nothing(index_elements=["release_code"])
        )
        conn.execute(stmt)

        for ver in versions:
            stmt = (
                insert(t.release_members)
                .values(
                    id=str(uuid.uuid5(uuid.NAMESPACE_DNS, f"{release.id}:{ver.id}")),
                    release_id=release.id,
                    rule_version_id=ver.id,
                    rule_id=ver.rule_id,
                )
                .on_conflict_do_nothing(index_elements=["release_id", "rule_id"])
            )
            conn.execute(stmt)

        return release

    def get_active_release(
        self, conn: Connection | None = None
    ) -> tuple[RuleReleaseRecord, list[RuleVersionRecord]]:
        """Fetch the active rule release and its compiled member rule versions."""
        if conn is not None:
            return self._get_active_release_conn(conn)
        with self.engine.begin() as connection:
            return self._get_active_release_conn(connection)

    def _get_active_release_conn(
        self, conn: Connection
    ) -> tuple[RuleReleaseRecord, list[RuleVersionRecord]]:
        rel_row = (
            conn.execute(select(t.rule_releases).where(t.rule_releases.c.is_active.is_(True)))
            .mappings()
            .first()
        )

        if not rel_row:
            # Seed default if none active
            self._seed_with_conn(conn)
            rel_row = (
                conn.execute(select(t.rule_releases).where(t.rule_releases.c.is_active.is_(True)))
                .mappings()
                .one()
            )

        members = (
            conn.execute(
                select(t.rule_versions)
                .join(
                    t.release_members, t.release_members.c.rule_version_id == t.rule_versions.c.id
                )
                .where(t.release_members.c.release_id == rel_row["id"])
            )
            .mappings()
            .all()
        )

        rule_versions: list[RuleVersionRecord] = []
        member_rule_ids: list[str] = []
        for m in members:
            rule_versions.append(
                RuleVersionRecord(
                    id=m["id"],
                    rule_id=m["rule_id"],
                    version=m["version"],
                    content_hash=m["content_hash"],
                    source_id=m["source_id"],
                    clause=m["clause"],
                    printed_page=m["printed_page"],
                    pdf_page=m["pdf_page"],
                    page_offset=m["page_offset"],
                    applicability=m["applicability"] or {},
                    parameters=m["parameters"] or {},
                    dsl_expression=m["dsl_expression"] or {},
                    status=PublicationState(m["status"]),
                    production_enabled=m["production_enabled"],
                    adverse_action_allowed=m["adverse_action_allowed"],
                )
            )
            member_rule_ids.append(m["rule_id"])

        release = RuleReleaseRecord(
            id=rel_row["id"],
            release_code=rel_row["release_code"],
            version=rel_row["version"],
            academic_cycle=rel_row["academic_cycle"],
            content_hash=rel_row["content_hash"],
            status=PublicationState(rel_row["status"]),
            approved_by=rel_row["approved_by"],
            is_active=rel_row["is_active"],
            member_rule_ids=member_rule_ids,
        )
        return release, rule_versions
