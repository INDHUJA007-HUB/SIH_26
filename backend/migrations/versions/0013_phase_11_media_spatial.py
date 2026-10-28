"""Phase 11 media evidence, frame sampling, equipment detection, and floor plan reconciliation.

Revision ID: 0013_phase_11_media_spatial
Revises: 0012_phase_10_alerts_audit
Create Date: 2026-10-28
"""

import sqlalchemy as sa
from alembic import op

revision = "0013_phase_11_media_spatial"
down_revision = "0012_phase_10_alerts_audit"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 1. media_metadata (video ffprobe inspection, role-specific checks, EXIF/GPS preservation)
    op.create_table(
        "media_metadata",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("institution_id", sa.String(36), nullable=False),
        sa.Column("evidence_id", sa.String(36), nullable=False),
        sa.Column("evidence_version_id", sa.String(36), nullable=False),
        sa.Column("media_type", sa.String(50), nullable=False),
        sa.Column("video_role", sa.String(50), nullable=False, server_default="NONE"),
        sa.Column("duration_seconds", sa.Float(), nullable=False, server_default="0"),
        sa.Column("dimensions", sa.JSON()),
        sa.Column("codec", sa.String(50)),
        sa.Column("frame_rate", sa.Float()),
        sa.Column("bitrate_kbps", sa.Integer()),
        sa.Column("gps_metadata", sa.JSON()),
        sa.Column("has_gps", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("metadata_status", sa.String(50), nullable=False, server_default="VALID"),
        sa.Column("duration_policy_result", sa.JSON()),
        sa.Column("exif_raw", sa.JSON()),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.ForeignKeyConstraint(
            ["institution_id"],
            ["institutions.id"],
            name="fk_media_metadata_institution",
        ),
        sa.ForeignKeyConstraint(
            ["evidence_version_id"],
            ["evidence_versions.id"],
            name="fk_media_metadata_version",
        ),
    )

    # 2. media_sampled_frames (deterministic capped frame sampling, timestamps, perceptual hashes)
    op.create_table(
        "media_sampled_frames",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("institution_id", sa.String(36), nullable=False),
        sa.Column("media_metadata_id", sa.String(36), nullable=False),
        sa.Column("evidence_version_id", sa.String(36), nullable=False),
        sa.Column("frame_index", sa.Integer(), nullable=False),
        sa.Column("timestamp_seconds", sa.Float(), nullable=False),
        sa.Column("perceptual_hash", sa.String(64), nullable=False),
        sa.Column("difference_hash", sa.String(64)),
        sa.Column("average_hash", sa.String(64)),
        sa.Column("frame_storage_key", sa.String(255)),
        sa.Column("is_keyframe", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.ForeignKeyConstraint(
            ["institution_id"],
            ["institutions.id"],
            name="fk_media_frames_institution",
        ),
        sa.ForeignKeyConstraint(
            ["media_metadata_id"],
            ["media_metadata.id"],
            name="fk_media_frames_metadata",
        ),
        sa.ForeignKeyConstraint(
            ["evidence_version_id"],
            ["evidence_versions.id"],
            name="fk_media_frames_version",
        ),
    )

    # 3. media_similarity_matches (perceptual hash near-duplicates, repeated scene advisories)
    op.create_table(
        "media_similarity_matches",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("institution_id", sa.String(36), nullable=False),
        sa.Column("source_evidence_version_id", sa.String(36), nullable=False),
        sa.Column("target_evidence_version_id", sa.String(36), nullable=False),
        sa.Column("source_frame_id", sa.String(36)),
        sa.Column("target_frame_id", sa.String(36)),
        sa.Column("similarity_score", sa.Float(), nullable=False),
        sa.Column("hamming_distance", sa.Integer(), nullable=False),
        sa.Column("match_type", sa.String(50), nullable=False),
        sa.Column("scope", sa.String(50), nullable=False, server_default="INTRA_APPLICATION"),
        sa.Column(
            "advisory_disposition",
            sa.String(50),
            nullable=False,
            server_default="POTENTIAL_REPEATED_SCENE",
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.ForeignKeyConstraint(
            ["institution_id"],
            ["institutions.id"],
            name="fk_media_similarity_institution",
        ),
        sa.ForeignKeyConstraint(
            ["source_evidence_version_id"],
            ["evidence_versions.id"],
            name="fk_media_similarity_src_ver",
        ),
        sa.ForeignKeyConstraint(
            ["target_evidence_version_id"],
            ["evidence_versions.id"],
            name="fk_media_similarity_tgt_ver",
        ),
        sa.ForeignKeyConstraint(
            ["source_frame_id"],
            ["media_sampled_frames.id"],
            name="fk_media_similarity_src_frame",
        ),
        sa.ForeignKeyConstraint(
            ["target_frame_id"],
            ["media_sampled_frames.id"],
            name="fk_media_similarity_tgt_frame",
        ),
    )

    # 4. equipment_detections (room-level visible candidate detection, bounding boxes,
    # advisory findings)
    op.create_table(
        "equipment_detections",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("institution_id", sa.String(36), nullable=False),
        sa.Column("application_id", sa.String(36), nullable=False),
        sa.Column("evidence_version_id", sa.String(36), nullable=False),
        sa.Column("room_identifier", sa.String(100), nullable=False),
        sa.Column(
            "equipment_category",
            sa.String(50),
            nullable=False,
            server_default="WORKSTATION",
        ),
        sa.Column("declared_quantity", sa.Integer(), nullable=False),
        sa.Column(
            "model_mode",
            sa.String(50),
            nullable=False,
            server_default="INFERENCE_RUN",
        ),
        sa.Column("model_name", sa.String(100), nullable=False),
        sa.Column("model_version", sa.String(50), nullable=False),
        sa.Column("detected_candidate_count", sa.Integer(), nullable=False),
        sa.Column("detected_boxes", sa.JSON(), nullable=False),
        sa.Column("confidence_score", sa.Float(), nullable=False, server_default="0.85"),
        sa.Column("coverage_assessment", sa.JSON(), nullable=False),
        sa.Column("advisory_finding", sa.Text(), nullable=False),
        sa.Column("human_correction", sa.JSON()),
        sa.Column(
            "status",
            sa.String(50),
            nullable=False,
            server_default="ADVISORY_PENDING_REVIEW",
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.ForeignKeyConstraint(
            ["institution_id"],
            ["institutions.id"],
            name="fk_equipment_detections_institution",
        ),
        sa.ForeignKeyConstraint(
            ["application_id"],
            ["applications.id"],
            name="fk_equipment_detections_application",
        ),
        sa.ForeignKeyConstraint(
            ["evidence_version_id"],
            ["evidence_versions.id"],
            name="fk_equipment_detections_evidence_ver",
        ),
    )

    # 5. floor_plan_reconciliations (spatial room schedule matching against floor plan drawings)
    op.create_table(
        "floor_plan_reconciliations",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("institution_id", sa.String(36), nullable=False),
        sa.Column("application_id", sa.String(36), nullable=False),
        sa.Column("evidence_version_id", sa.String(36), nullable=False),
        sa.Column("plan_name", sa.String(100), nullable=False),
        sa.Column("total_declared_area_sqm", sa.Float(), nullable=False),
        sa.Column("total_measured_area_sqm", sa.Float(), nullable=False),
        sa.Column("declared_spaces", sa.JSON(), nullable=False),
        sa.Column("identified_spaces", sa.JSON(), nullable=False),
        sa.Column("matched_spaces", sa.JSON(), nullable=False),
        sa.Column("discrepancies", sa.JSON(), nullable=False),
        sa.Column(
            "reconciliation_status",
            sa.String(50),
            nullable=False,
            server_default="RECONCILED",
        ),
        sa.Column("notes", sa.Text()),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.ForeignKeyConstraint(
            ["institution_id"],
            ["institutions.id"],
            name="fk_floor_plan_institution",
        ),
        sa.ForeignKeyConstraint(
            ["application_id"],
            ["applications.id"],
            name="fk_floor_plan_application",
        ),
        sa.ForeignKeyConstraint(
            ["evidence_version_id"],
            ["evidence_versions.id"],
            name="fk_floor_plan_evidence_ver",
        ),
    )

    # Secondary indexes
    op.create_index(
        "ix_media_metadata_evidence",
        "media_metadata",
        ["evidence_id", "evidence_version_id"],
    )
    op.create_index(
        "ix_sampled_frames_meta",
        "media_sampled_frames",
        ["media_metadata_id", "frame_index"],
    )
    op.create_index(
        "ix_sampled_frames_phash",
        "media_sampled_frames",
        ["perceptual_hash"],
    )
    op.create_index(
        "ix_similarity_matches_source",
        "media_similarity_matches",
        ["source_evidence_version_id"],
    )
    op.create_index(
        "ix_similarity_matches_target",
        "media_similarity_matches",
        ["target_evidence_version_id"],
    )
    op.create_index(
        "ix_equipment_detections_app_room",
        "equipment_detections",
        ["application_id", "room_identifier"],
    )
    op.create_index(
        "ix_floor_plan_reconciliations_app",
        "floor_plan_reconciliations",
        ["application_id"],
    )

    # RLS Policies and owner indexes
    p11_tables = [
        "media_metadata",
        "media_sampled_frames",
        "media_similarity_matches",
        "equipment_detections",
        "floor_plan_reconciliations",
    ]
    elevated_check = "(wb.elevated() AND (wb.has_role('supervisor') OR wb.has_role('auditor')))"

    for tbl in p11_tables:
        op.create_index(f"ix_{tbl}_owner_time", tbl, ["institution_id", "created_at", "id"])
        op.execute(f"ALTER TABLE {tbl} ENABLE ROW LEVEL SECURITY")
        op.execute(f"ALTER TABLE {tbl} FORCE ROW LEVEL SECURITY")

        # Table-specific can_access check depending on whether application_id column exists
        if tbl in ("equipment_detections", "floor_plan_reconciliations"):
            app_arg = "application_id"
        else:
            app_arg = "NULL"

        can_read = (
            f"(wb.can_access(institution_id, {app_arg}, false) OR wb.manages(institution_id) "
            f"OR {elevated_check})"
        )
        can_write = (
            f"(wb.can_access(institution_id, {app_arg}, true) OR wb.manages(institution_id) "
            f"OR {elevated_check})"
        )

        op.execute(f"CREATE POLICY {tbl}_read ON {tbl} FOR SELECT TO wb_app USING ({can_read})")
        op.execute(
            f"CREATE POLICY {tbl}_write ON {tbl} FOR ALL TO wb_app "
            f"USING ({can_write}) "
            f"WITH CHECK ({can_write})"
        )
        op.execute(
            f"CREATE POLICY worker_{tbl} ON {tbl} FOR ALL TO wb_worker, wb_scanner, wb_relay "
            "USING (true) WITH CHECK (true)"
        )
        op.execute(
            f"GRANT SELECT, INSERT, UPDATE, DELETE ON {tbl} TO "
            "wb_app, wb_worker, wb_scanner, wb_relay, wb_security_owner"
        )


def downgrade() -> None:
    raise RuntimeError("Operational security changes require a reviewed forward migration")
