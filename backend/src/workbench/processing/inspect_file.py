"""One job per subprocess. The parser container has no network, credentials or database."""

import hashlib
import importlib
import json
import math
import os
import subprocess
import sys
import warnings
from pathlib import Path
from typing import Any

import pypdfium2
from PIL import Image
from pypdf import PdfReader
from pypdf.generic import ArrayObject, DictionaryObject, IndirectObject


def inspect(job_id: str) -> dict[str, Any]:
    import uuid

    if str(uuid.UUID(job_id)) != job_id:
        raise ValueError("INVALID_JOB_ID")
    source = Path("/jobs/in") / (job_id + ".bin")
    specification = json.loads((Path("/jobs/in") / (job_id + ".json")).read_text())
    destination = Path("/jobs/out") / job_id
    destination.mkdir(exist_ok=True)
    resource: Any = importlib.import_module("resource")  # Linux-only, networkless parser container.
    resource.setrlimit(resource.RLIMIT_CPU, (20, 20))
    resource.setrlimit(resource.RLIMIT_AS, (768 * 1024 * 1024, 768 * 1024 * 1024))
    resource.setrlimit(resource.RLIMIT_FSIZE, (32 * 1024 * 1024, 32 * 1024 * 1024))
    resource.setrlimit(resource.RLIMIT_NOFILE, (64, 64))
    if source.stat().st_size != specification["size"]:
        raise ValueError("SIZE_MISMATCH")
    with source.open("rb") as file:
        digest = hashlib.file_digest(file, "sha256").hexdigest()
    if digest != specification["sha256"]:
        raise ValueError("CHECKSUM_MISMATCH")
    with source.open("rb") as file:
        magic = file.read(32)
    media_type = specification["media_type"]
    derivatives: list[dict[str, Any]] = []
    metadata = {}
    page_count = 0

    def save_preview(image: Image.Image, page: int) -> None:
        image.thumbnail((1600, 1600))
        output = destination / f"{page}.png"
        image.convert("RGB").save(output, format="PNG")
        derivatives.append(
            {
                "filename": output.name,
                "page": page,
                "kind": "PAGE",
                "size_bytes": output.stat().st_size,
                "sha256": hashlib.sha256(output.read_bytes()).hexdigest(),
                "metadata": {
                    "width": image.width,
                    "height": image.height,
                    "coordinate_basis": "preview_pixels",
                },
            }
        )
        if sum(item["size_bytes"] for item in derivatives) > 48 * 1024 * 1024:
            raise ValueError("DERIVATIVE_BUDGET_EXCEEDED")

    if media_type == "application/pdf":
        if not magic.startswith(b"%PDF-"):
            raise ValueError("MIME_MISMATCH")
        reader = PdfReader(source, strict=True)
        if reader.is_encrypted:
            raise ValueError("ENCRYPTED_PDF_UNSUPPORTED")
        page_count = len(reader.pages)
        if not 1 <= page_count <= specification["max_pdf_pages"]:
            raise ValueError("PAGE_LIMIT")
        dangerous = {
            "/JavaScript",
            "/JS",
            "/Launch",
            "/EmbeddedFile",
            "/RichMedia",
            "/OpenAction",
            "/AA",
            "/XFA",
        }
        count = 0

        def reject_active(value: Any, depth: int = 0) -> None:
            if depth > 50:
                raise ValueError("PDF_OBJECT_LIMIT")
            if isinstance(value, DictionaryObject):
                if dangerous.intersection(value):
                    raise ValueError("PDF_ACTIVE_CONTENT")
                for child in value.values():
                    if not isinstance(child, IndirectObject):
                        reject_active(child, depth + 1)
            elif isinstance(value, ArrayObject):
                for child in value:
                    if not isinstance(child, IndirectObject):
                        reject_active(child, depth + 1)

        reject_active(reader.trailer)
        for generation, entries in reader.xref.items():
            for number in entries:
                if number == 0:
                    continue
                count += 1
                if count > 50000:
                    raise ValueError("PDF_OBJECT_LIMIT")
                value = reader.get_object(IndirectObject(number, generation, reader))
                reject_active(value)
        for number in reader.xref_objStm:
            count += 1
            if count > 50000:
                raise ValueError("PDF_OBJECT_LIMIT")
            reject_active(reader.get_object(IndirectObject(number, 0, reader)))
        document = pypdfium2.PdfDocument(source)
        try:
            for index in range(page_count):
                page = document[index]
                width, height = page.get_size()
                if not 1 <= width <= 3000 or not 1 <= height <= 3000:
                    raise ValueError("PAGE_DIMENSION_LIMIT")
                scale = min(1.3, 1600 / max(width, height))
                bitmap = page.render(scale=scale)
                image = bitmap.to_pil()
                save_preview(image, index + 1)
                image.close()
                bitmap.close()
                page.close()
        finally:
            document.close()
        metadata = {"page_count": page_count, "parser_profile": "pdf-inspection-v1"}
    elif media_type in {"image/png", "image/jpeg"}:
        expected = (
            magic.startswith(b"\x89PNG\r\n\x1a\n")
            if media_type == "image/png"
            else magic.startswith(b"\xff\xd8\xff")
        )
        if not expected:
            raise ValueError("MIME_MISMATCH")
        Image.MAX_IMAGE_PIXELS = 20_000_000
        warnings.simplefilter("error", Image.DecompressionBombWarning)
        with Image.open(source) as image:
            if getattr(image, "n_frames", 1) != 1:
                raise ValueError("ANIMATED_IMAGE_UNSUPPORTED")
            image.verify()
        with Image.open(source) as image:
            image.load()
            metadata = {"width": image.width, "height": image.height}
            save_preview(image, 1)
        page_count = 1
    elif media_type == "video/mp4":
        if magic[4:8] != b"ftyp":
            raise ValueError("MIME_MISMATCH")
        completed = subprocess.run(  # noqa: S603 -- fixed executable/flags; validated local UUID path.
            [
                "/usr/local/bin/ffprobe",
                "-v",
                "error",
                "-protocol_whitelist",
                "file",
                "-show_entries",
                "format=duration:stream=codec_type,codec_name,width,height",
                "-of",
                "json",
                str(source),
            ],
            capture_output=True,
            timeout=10,
            check=True,
        )
        result = json.loads(completed.stdout)
        duration = float(result.get("format", {}).get("duration", "nan"))
        if not math.isfinite(duration) or not 0 < duration <= specification["max_video_seconds"]:
            raise ValueError("VIDEO_DURATION_LIMIT")
        streams = result.get("streams", [])
        if not any(item.get("codec_type") == "video" for item in streams):
            raise ValueError("VIDEO_STREAM_MISSING")
        metadata = {"duration_seconds": duration, "streams": streams}
    else:
        raise ValueError("MEDIA_TYPE_UNSUPPORTED")
    return {
        "status": "ACCEPTED",
        "media_type": media_type,
        "page_count": page_count,
        "metadata": metadata,
        "derivatives": derivatives,
        "sha256": digest,
    }


if __name__ == "__main__":
    job = sys.argv[1]
    try:
        result = inspect(job)
    except ValueError as error:
        reasons = {
            "INVALID_JOB_ID",
            "SIZE_MISMATCH",
            "CHECKSUM_MISMATCH",
            "MIME_MISMATCH",
            "ENCRYPTED_PDF_UNSUPPORTED",
            "PAGE_LIMIT",
            "PDF_OBJECT_LIMIT",
            "PDF_ACTIVE_CONTENT",
            "PAGE_DIMENSION_LIMIT",
            "DERIVATIVE_BUDGET_EXCEEDED",
            "ANIMATED_IMAGE_UNSUPPORTED",
            "VIDEO_DURATION_LIMIT",
            "VIDEO_STREAM_MISSING",
            "MEDIA_TYPE_UNSUPPORTED",
        }
        result = {
            "status": "REJECTED",
            "reason": str(error) if str(error) in reasons else "MALFORMED_OR_RESOURCE_LIMIT",
        }
    except Exception:
        result = {"status": "REJECTED", "reason": "MALFORMED_OR_RESOURCE_LIMIT"}
    target = Path("/jobs/out") / (job + ".result.json")
    temporary = target.with_suffix(".tmp")
    temporary.write_text(json.dumps(result), encoding="utf-8")
    os.replace(temporary, target)
