"""Phase 11: Media evidence, frame sampling, advisory visible equipment detection,
and spatial floor plan reconciliation tests.
"""

from __future__ import annotations

import base64
import io
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from PIL import Image
from sqlalchemy import insert, select, update

from workbench.adapters import tables as t
from workbench.modules.media_analysis.contracts import (
    EquipmentCategory,
    EquipmentDetectionStatus,
    FloorPlanStatus,
    ModelMode,
    VideoRole,
    VideoRolePolicy,
)
from workbench.modules.media_analysis.service import (
    compute_average_hash,
    compute_difference_hash,
    generate_contact_sheet,
    hamming_distance,
    sample_video_frames,
    validate_video_duration_policy,
)

pytestmark = pytest.mark.integration


def _create_synthetic_image(color: tuple[int, int, int] = (100, 150, 200)) -> bytes:
    img = Image.new("RGB", (640, 480), color=color)
    out = io.BytesIO()
    img.save(out, format="JPEG")
    return out.getvalue()


def _setup_evidence_records(h, inst_id: str, app_id: str) -> tuple[str, str]:
    slot_id = str(uuid4())
    upload_id = str(uuid4())
    ev_ver_id = str(uuid4())

    with h.owner.begin() as conn:
        conn.execute(
            insert(t.slots).values(
                id=slot_id,
                institution_id=inst_id,
                application_id=app_id,
                code="FACILITY_MEDIA_" + slot_id[:8],
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
                filename="lab101.mp4",
                media_type="video/mp4",
                expected_size=1048576,
                expected_sha256="0" * 64,
                object_key=f"quarantine/{ev_ver_id}.mp4",
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
                quarantine_key=f"quarantine/{ev_ver_id}.mp4",
                quarantine_version="1",
                sha256="0" * 64,
                media_type="video/mp4",
                filename="lab101.mp4",
                size_bytes=1048576,
                status="QUARANTINED",
                clean_key=None,
                clean_version=None,
                metadata={"type": "VIDEO"},
            )
        )
        conn.execute(
            update(t.evidence)
            .where(t.evidence.c.id == ev_ver_id)
            .values(
                status="ACCEPTED",
                clean_key=f"clean/{ev_ver_id}.mp4",
                clean_version="1",
            )
        )
    return ev_ver_id, ev_ver_id


def test_video_role_duration_policy_differentiation(h):
    """Subphase 11.1: The 1-2 minute website disclosure and contextual EVC walkthrough
    requirements must NOT share one global duration constant.
    """
    disc_policy = VideoRolePolicy.get_policy(VideoRole.WEBSITE_DISCLOSURE)
    evc_policy = VideoRolePolicy.get_policy(VideoRole.EVC_WALKTHROUGH)
    supp_policy = VideoRolePolicy.get_policy(VideoRole.SUPPLEMENTARY_EVIDENCE)

    # Invariant: Distinct non-overlapping policy thresholds
    assert (disc_policy.min_seconds, disc_policy.max_seconds) == (60.0, 120.0)
    assert (evc_policy.min_seconds, evc_policy.max_seconds) == (180.0, 1800.0)
    assert (supp_policy.min_seconds, supp_policy.max_seconds) == (5.0, 600.0)

    # Website disclosure: 90s is compliant; 45s and 150s are invalid
    res_disc_90 = validate_video_duration_policy(VideoRole.WEBSITE_DISCLOSURE.value, 90.0)
    assert res_disc_90["compliant"] is True
    assert res_disc_90["discrepancy"] is None

    res_disc_45 = validate_video_duration_policy(VideoRole.WEBSITE_DISCLOSURE.value, 45.0)
    assert res_disc_45["compliant"] is False
    assert "falls below minimum required duration (60.0s)" in res_disc_45["discrepancy"]

    res_disc_150 = validate_video_duration_policy(VideoRole.WEBSITE_DISCLOSURE.value, 150.0)
    assert res_disc_150["compliant"] is False
    assert "exceeds maximum allowed duration (120.0s)" in res_disc_150["discrepancy"]

    # EVC walkthrough: 900s is compliant; 90s is invalid
    res_evc_900 = validate_video_duration_policy(VideoRole.EVC_WALKTHROUGH.value, 900.0)
    assert res_evc_900["compliant"] is True

    res_evc_90 = validate_video_duration_policy(VideoRole.EVC_WALKTHROUGH.value, 90.0)
    assert res_evc_90["compliant"] is False
    assert "falls below minimum required duration (180.0s)" in res_evc_90["discrepancy"]


def test_missing_gps_exif_handled_as_unavailable_metadata_never_error(h):
    """Subphase 11.1 / Exit gate: Missing GPS or EXIF is recorded as unavailable metadata
    and NEVER flagged as source mismatch or compliance failure.
    """
    app = h.create()
    inst_id = h.institutions["a"]
    app_id = app["id"]
    ev_id, ev_ver_id = _setup_evidence_records(h, inst_id, app_id)

    raw_image_bytes = _create_synthetic_image()
    b64_img = base64.b64encode(raw_image_bytes).decode("ascii")

    resp = h.call(
        "POST",
        f"/api/v1/evidence/{ev_id}/media-analysis",
        json={
            "evidence_version_id": ev_ver_id,
            "media_type": "image/jpeg",
            "video_role": VideoRole.NONE.value,
            "duration_seconds": 0.0,
            "image_bytes_base64": b64_img,
        },
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()

    # Missing GPS is handled honestly as unavailable metadata, NOT an error
    assert data["has_gps"] is False
    assert data["gps_metadata"] is None
    assert data["metadata_status"] == "VALID"  # Valid image without GPS
    assert data["sampled_frame_count"] == 1


def test_frame_sampling_and_contact_sheet_generation(h):
    """Subphase 11.2: Deterministic capped frame sampling and composite contact sheet generation."""
    # 1. Deterministic sampler test: 120s video sampled every 10s yields 13 frames <= 180 cap
    sampled = sample_video_frames(120.0, max_frames=180, interval_seconds=10.0)
    assert len(sampled) == 13
    assert sampled[0] == (0, 0.0)
    assert sampled[-1] == (12, 120.0)

    # 2. Contact sheet generator test
    frame_images: list[tuple[float, Image.Image]] = []
    for idx, ts in sampled:
        img = Image.new("RGB", (160, 90), color=(idx * 15, 80, 120))
        frame_images.append((ts, img))

    sheet_png = generate_contact_sheet(frame_images, cols=3)
    assert sheet_png.startswith(b"\x89PNG\r\n\x1a\n")

    # Verify Pillow can open the generated contact sheet
    opened_sheet = Image.open(io.BytesIO(sheet_png))
    assert opened_sheet.format == "PNG"
    assert opened_sheet.width == 3 * 160
    assert opened_sheet.height == 5 * 90  # 13 items in 3 columns = 5 rows


def test_perceptual_hash_and_near_duplicate_candidate_detection(h):
    """Subphase 11.2: Perceptual hashing (aHash/dHash) and near-duplicate candidate detection."""
    app = h.create()
    inst_id = h.institutions["a"]
    app_id = app["id"]

    ev_id1, ev_ver1 = _setup_evidence_records(h, inst_id, app_id)
    ev_id2, ev_ver2 = _setup_evidence_records(h, inst_id, app_id)

    # Create base image
    base_img = Image.new("RGB", (200, 200), color=(120, 130, 140))
    # Create near-duplicate image with very minor pixel modification
    modified_img = Image.new("RGB", (200, 200), color=(122, 131, 140))

    ahash1 = compute_average_hash(base_img)
    ahash2 = compute_average_hash(modified_img)
    dhash1 = compute_difference_hash(base_img)
    dhash2 = compute_difference_hash(modified_img)

    dist_a = hamming_distance(ahash1, ahash2)
    dist_d = hamming_distance(dhash1, dhash2)
    assert dist_a <= 5, f"aHash distance {dist_a} should be <= 5"
    assert dist_d <= 5, f"dHash distance {dist_d} should be <= 5"

    b64_1 = base64.b64encode(_create_synthetic_image((120, 130, 140))).decode("ascii")
    b64_2 = base64.b64encode(_create_synthetic_image((120, 130, 140))).decode("ascii")

    h.call(
        "POST",
        f"/api/v1/evidence/{ev_id1}/media-analysis",
        json={
            "evidence_version_id": ev_ver1,
            "media_type": "image/jpeg",
            "image_bytes_base64": b64_1,
        },
    )
    h.call(
        "POST",
        f"/api/v1/evidence/{ev_id2}/media-analysis",
        json={
            "evidence_version_id": ev_ver2,
            "media_type": "image/jpeg",
            "image_bytes_base64": b64_2,
        },
    )

    # Check similarity endpoint: near duplicates produce advisory candidates
    sim_resp = h.call(
        "POST",
        f"/api/v1/evidence/{ev_id1}/similarity-check",
        json={"target_evidence_version_id": ev_ver2},
    )
    assert sim_resp.status_code == 200, sim_resp.text
    matches = sim_resp.json()
    assert len(matches) >= 1
    match = matches[0]
    assert match["hamming_distance"] <= 5
    assert match["advisory_disposition"] in (
        "IDENTICAL_FRAME_REUSED",
        "POTENTIAL_REPEATED_SCENE_ADVISORY",
    )


def test_equipment_detection_advisory_wording_and_partial_view_bounds(h):
    """Subphase 11.3 / Exit gate: Equipment candidate detection with normalized bounding boxes,
    coverage assessment, count uncertainty, and required advisory wording.
    Single-view photographs are NEVER treated as complete inventory!
    """
    app = h.create()
    inst_id = h.institutions["a"]
    app_id = app["id"]
    ev_id, ev_ver_id = _setup_evidence_records(h, inst_id, app_id)

    raw_img = _create_synthetic_image((180, 180, 190))
    b64_img = base64.b64encode(raw_img).decode("ascii")

    resp = h.call(
        "POST",
        f"/api/v1/applications/{app_id}/equipment-detection",
        json={
            "evidence_version_id": ev_ver_id,
            "room_identifier": "Lab-101",
            "declared_quantity": 20,
            "equipment_category": EquipmentCategory.WORKSTATION.value,
            "model_mode": ModelMode.INFERENCE_RUN.value,
            "image_bytes_base64": b64_img,
        },
    )
    assert resp.status_code == 200, resp.text
    detection = resp.json()

    assert detection["application_id"] == app_id
    assert detection["room_identifier"] == "Lab-101"
    assert detection["declared_quantity"] == 20
    assert detection["status"] == EquipmentDetectionStatus.ADVISORY_PENDING_REVIEW.value

    boxes = detection["detected_boxes"]
    assert len(boxes) > 0
    for b in boxes:
        # Bounding boxes must be [ymin, xmin, ymax, xmax] normalized 0.0 - 1.0
        box = b["box"]
        assert len(box) == 4
        assert 0.0 <= box[0] <= 1.0
        assert 0.0 <= box[1] <= 1.0
        assert 0.0 <= box[2] <= 1.0
        assert 0.0 <= box[3] <= 1.0
        assert b["label"] == "workstation"

    # Coverage assessment verifies partial view (~65%)
    cov = detection["coverage_assessment"]
    assert cov["coverage_percent"] == 65
    assert cov["camera_perspective"] == "FRONT_LEFT_OBLIQUE"
    assert cov["occlusion_observed"] is True

    # Check calibrated advisory wording: partial view does not establish non-existence
    adv = detection["advisory_finding"]
    det_count = detection["detected_candidate_count"]
    diff = 20 - det_count
    expected_wording = (
        f"Advisory discrepancy: {det_count} visible workstation candidates detected in "
        f"single-view image against declared inventory of 20 for room 'Lab-101'. "
        f"Single-view photograph provides partial coverage (~65%) and does not establish "
        f"non-existence of remaining {diff} unit(s). "
        f"Additional camera angles or physical inspection required."
    )
    assert adv == expected_wording, f"Expected advisory wording mismatch: {adv}"


def test_audited_human_count_correction_preserves_model_inference(h):
    """Subphase 11.3 / Exit gate: Audited human count correction records officer ID and reason
    without mutating the original model inference or bounding boxes.
    """
    app = h.create()
    inst_id = h.institutions["a"]
    app_id = app["id"]
    ev_id, ev_ver_id = _setup_evidence_records(h, inst_id, app_id)

    raw_img = _create_synthetic_image((150, 160, 170))
    b64_img = base64.b64encode(raw_img).decode("ascii")

    det_resp = h.call(
        "POST",
        f"/api/v1/applications/{app_id}/equipment-detection",
        json={
            "evidence_version_id": ev_ver_id,
            "room_identifier": "Lab-202",
            "declared_quantity": 25,
            "equipment_category": EquipmentCategory.WORKSTATION.value,
            "image_bytes_base64": b64_img,
        },
    )
    assert det_resp.status_code == 200
    detection_id = det_resp.json()["id"]
    original_candidate_count = det_resp.json()["detected_candidate_count"]
    original_boxes = det_resp.json()["detected_boxes"]

    # Submit audited human correction
    corr_resp = h.call(
        "POST",
        f"/api/v1/equipment-detections/{detection_id}/corrections",
        json={
            "corrected_count": 25,
            "reason": (
                "Verified 4 additional workstations situated behind "
                "support column from alternate angle."
            ),
        },
    )
    assert corr_resp.status_code == 200, corr_resp.text
    corr_data = corr_resp.json()
    assert corr_data["status"] == EquipmentDetectionStatus.OFFICER_CONFIRMED.value
    assert corr_data["human_correction"]["corrected_count"] == 25
    assert corr_data["human_correction"]["original_count"] == original_candidate_count
    assert "Verified 4 additional workstations" in corr_data["human_correction"]["reason"]

    # Invariant: Query database directly and verify original model inference is unmutated
    with h.owner.connect() as conn:
        row = (
            conn.execute(
                select(t.equipment_detections).where(t.equipment_detections.c.id == detection_id)
            )
            .mappings()
            .first()
        )
        assert row["detected_candidate_count"] == original_candidate_count
        assert row["detected_boxes"] == original_boxes
        assert row["status"] == EquipmentDetectionStatus.OFFICER_CONFIRMED.value
        assert row["human_correction"]["corrected_count"] == 25


def test_floor_plan_spatial_reconciliation_and_area_tolerance(h):
    """Subphase 11.4 / Exit gate: Spatial floor plan schedule reconciliation
    within 5% area tolerance.
    """
    app = h.create()
    inst_id = h.institutions["a"]
    app_id = app["id"]
    ev_id, ev_ver_id = _setup_evidence_records(h, inst_id, app_id)

    declared_spaces = [
        {"room_identifier": "Classroom-A", "room_type": "CLASSROOM", "declared_area_sqm": 66.0},
        {"room_identifier": "Physics-Lab", "room_type": "LABORATORY", "declared_area_sqm": 80.0},
        {"room_identifier": "Admin-Office", "room_type": "OFFICE", "declared_area_sqm": 40.0},
    ]

    identified_spaces = [
        # Classroom-A: 68.0 sqm vs 66.0 declared (+3.0% diff -> within 5% tolerance -> MATCHED)
        {"space_label": "Classroom-A", "measured_area_sqm": 68.0},
        # Physics-Lab: 65.0 sqm vs 80.0 declared (-18.75% diff -> >5% tolerance -> AREA_DISCREPANCY)
        {"space_label": "Physics-Lab", "measured_area_sqm": 65.0},
        # Admin-Office is omitted on plan -> MISSING_ON_PLAN
    ]

    resp = h.call(
        "POST",
        f"/api/v1/applications/{app_id}/floor-plan-reconciliation",
        json={
            "evidence_version_id": ev_ver_id,
            "plan_name": "Main Academic Block Floor 1 Drawing",
            "declared_spaces": declared_spaces,
            "identified_spaces": identified_spaces,
        },
    )
    assert resp.status_code == 200, resp.text
    rec = resp.json()

    assert rec["application_id"] == app_id
    assert rec["total_declared_area_sqm"] == 186.0
    assert rec["total_measured_area_sqm"] == 133.0
    assert rec["reconciliation_status"] == FloorPlanStatus.DISCREPANCIES_FLAGGED.value

    # Exactly 1 space matched (within 5% tolerance)
    assert len(rec["matched_spaces"]) == 1
    assert rec["matched_spaces"][0]["room_identifier"] == "Classroom-A"

    # Exactly 2 discrepancies: 1 AREA_DISCREPANCY, 1 MISSING_ON_PLAN
    disc_types = [d["type"] for d in rec["discrepancies"]]
    assert "AREA_DISCREPANCY" in disc_types
    assert "MISSING_ON_PLAN" in disc_types


def test_phase_11_unassigned_officer_and_cross_tenant_denial(h):
    """Exit gate / Mandatory protocol: Unassigned officer and cross-tenant access denial.
    Unassigned officer gets 403 Forbidden; assigned officer gets 200 OK.
    """
    inst_a = h.institutions["a"]
    app = h.create(actor="a")
    app_id = app["id"]
    ev_id, ev_ver_id = _setup_evidence_records(h, inst_a, app_id)

    # 1. Populate an equipment detection and a floor plan reconciliation for Institution A
    with h.owner.begin() as conn:
        det_id = str(uuid4())
        rec_id = str(uuid4())
        now = datetime.now(UTC)
        conn.execute(
            insert(t.equipment_detections).values(
                id=det_id,
                institution_id=inst_a,
                application_id=app_id,
                evidence_version_id=ev_ver_id,
                room_identifier="Lab-Secret-A",
                equipment_category="WORKSTATION",
                declared_quantity=30,
                model_mode="INFERENCE_RUN",
                model_name="yolo-vision-room-detector",
                model_version="v2.4-lite",
                detected_candidate_count=20,
                detected_boxes=[],
                confidence_score=0.88,
                coverage_assessment={"coverage_percent": 65},
                advisory_finding="Advisory finding for Lab A",
                status="ADVISORY_PENDING_REVIEW",
                created_at=now,
            )
        )
        conn.execute(
            insert(t.floor_plan_reconciliations).values(
                id=rec_id,
                institution_id=inst_a,
                application_id=app_id,
                evidence_version_id=ev_ver_id,
                plan_name="Ground Floor Wing A",
                total_declared_area_sqm=100.0,
                total_measured_area_sqm=100.0,
                declared_spaces=[],
                identified_spaces=[],
                matched_spaces=[],
                discrepancies=[],
                reconciliation_status="RECONCILED",
                created_at=now,
            )
        )

    # 2. Unassigned officer attempts to access Institution A equipment & floor plans -> 403
    endpoints = [
        f"/api/v1/applications/{app_id}/equipment-detections",
        f"/api/v1/applications/{app_id}/floor-plan-reconciliations",
    ]
    for ep in endpoints:
        resp = h.call("GET", ep, actor="officer", mfa=True)
        assert resp.status_code in (403, 404), (
            f"Unassigned officer on {ep} expected 403/404, got {resp.status_code}"
        )

    # 3. Cross-tenant: Institution B actor attempts to access Institution A -> 403 Forbidden
    for ep in endpoints:
        resp_b = h.call("GET", ep, actor="b", mfa=False)
        assert resp_b.status_code in (403, 404), (
            f"Cross-tenant actor on {ep} expected 403/404, got {resp_b.status_code}"
        )

    # 4. Formally assign the officer specifically to this application in Institution A
    with h.owner.begin() as conn:
        conn.execute(
            insert(t.case_assignments).values(
                id=str(uuid4()),
                institution_id=inst_a,
                application_id=app_id,
                actor_id=h.actors["officer"],
                access_role="officer",
                granted_by=h.actors["admin"],
                reason=(
                    "Formal assignment to inspect Institution A equipment and spatial floor plans"
                ),
                expires_at=datetime.now(UTC) + timedelta(days=7),
            )
        )

    # 5. Formally assigned officer can now access Institution A equipment & floor plans -> 200 OK
    resp_eq = h.call(
        "GET", f"/api/v1/applications/{app_id}/equipment-detections", actor="officer", mfa=True
    )
    assert resp_eq.status_code == 200, resp_eq.text
    assert len(resp_eq.json()) >= 1
    assert resp_eq.json()[0]["room_identifier"] == "Lab-Secret-A"

    resp_fp = h.call(
        "GET",
        f"/api/v1/applications/{app_id}/floor-plan-reconciliations",
        actor="officer",
        mfa=True,
    )
    assert resp_fp.status_code == 200, resp_fp.text
    assert len(resp_fp.json()) >= 1
    assert resp_fp.json()[0]["plan_name"] == "Ground Floor Wing A"
