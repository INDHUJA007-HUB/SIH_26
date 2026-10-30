"""Actual media processing from admitted, hash-checked evidence bytes."""

import hashlib
import io
from typing import Any
from uuid import uuid4

from PIL import Image
from sqlalchemy import select, text
from temporalio import activity

from workbench.adapters import tables as t
from workbench.adapters.media_analysis_application_service import MediaAnalysisService
from workbench.adapters.object_storage import ObjectStorage
from workbench.modules.media_analysis.service import generate_contact_sheet
from workbench.platform.config import Settings
from workbench.platform.runtime_roles import build_runtime_engine
from workbench.processing.media_decoder import decode_video


@activity.defn
def process_media(event_id: str) -> dict[str, Any]:
    settings = Settings()
    engine = build_runtime_engine(settings.worker_database_url.get_secret_value(), "wb_worker")
    try:
        storage = ObjectStorage(settings)
        with engine.begin() as conn:
            event = conn.execute(select(t.outbox).where(t.outbox.c.id == event_id)).mappings().one()
            conn.execute(
                text("SELECT pg_advisory_xact_lock(hashtextextended(:key,0))"),
                {"key": "media:" + event["payload"]["evidence_id"]},
            )
            ev = (
                conn.execute(
                    select(t.evidence).where(
                        t.evidence.c.id == event["payload"]["evidence_id"],
                    )
                )
                .mappings()
                .one()
            )
            existing = (
                conn.execute(
                    select(t.media_metadata).where(
                        t.media_metadata.c.evidence_version_id == ev["id"],
                    )
                )
                .mappings()
                .first()
            )
            if existing:
                return {"media_metadata_id": existing["id"], "replayed": True}
            if ev["status"] != "ACCEPTED":
                raise ValueError("Only admitted evidence may be analyzed")
            source = storage.read(ev["clean_key"], ev["clean_version"], storage.clean)
            try:
                content = source.read(settings.max_upload_bytes + 1)
            finally:
                source.close()
            if (
                len(content) > settings.max_upload_bytes
                or hashlib.sha256(content).hexdigest() != ev["sha256"]
            ):
                raise ValueError("Evidence hash mismatch or processing limit exceeded")
            frames: list[tuple[float, bytes]] = []
            metadata: dict[str, Any] = {"duration_seconds": 0.0}
            if ev["media_type"] == "video/mp4":
                metadata, frames = decode_video(content)
            elif ev["media_type"] in {"image/png", "image/jpeg"}:
                frames = [(0.0, content)]
            else:
                raise ValueError("Unsupported media type")
            result = MediaAnalysisService(conn).inspect_and_store_media(
                institution_id=ev["institution_id"],
                evidence_id=ev["id"],
                evidence_version_id=ev["id"],
                media_type=ev["media_type"],
                video_role=event["payload"]["video_role"],
                image_bytes=content if ev["media_type"].startswith("image/") else None,
                decoded_frames=frames,
                **metadata,
            )
            images: list[tuple[float, Image.Image]] = [
                (timestamp, Image.open(io.BytesIO(data))) for timestamp, data in frames
            ]
            try:
                sheet = generate_contact_sheet(images)
            finally:
                for _, image in images:
                    image.close()
            key = f"derivatives/{ev['institution_id']}/{ev['id']}/contact-sheet.png"
            stored = storage.client.put_object(
                Bucket=storage.clean, Key=key, Body=sheet, ContentType="image/png"
            )
            conn.execute(
                t.derivatives.insert().values(
                    id=str(uuid4()),
                    institution_id=ev["institution_id"],
                    application_id=ev["application_id"],
                    evidence_id=ev["id"],
                    kind="CONTACT_SHEET",
                    page=0,
                    object_key=key,
                    object_version=stored["VersionId"],
                    sha256=hashlib.sha256(sheet).hexdigest(),
                    size_bytes=len(sheet),
                    media_type="image/png",
                    metadata={"frame_count": len(frames)},
                )
            )
            return result
    finally:
        engine.dispose()
