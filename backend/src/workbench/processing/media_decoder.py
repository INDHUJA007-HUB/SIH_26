"""Bounded local-file video decoding. Run only in the isolated media worker."""

import io
import json
import math
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Any

from PIL import Image


def decode_video(
    content: bytes, max_frames: int = 24
) -> tuple[dict[str, Any], list[tuple[float, bytes]]]:
    if not content or len(content) > 100 * 1024 * 1024 or not 1 <= max_frames <= 180:
        raise ValueError("Video exceeds processing limits")
    probe, decoder = shutil.which("ffprobe"), shutil.which("ffmpeg")
    if not probe or not decoder:
        raise ValueError("Video decoder unavailable; manual inspection required")
    with tempfile.TemporaryDirectory(prefix="workbench-media-") as folder:
        source = Path(folder) / "input.mp4"
        source.write_bytes(content)
        raw = subprocess.run(  # noqa: S603
            [
                probe,
                "-v",
                "error",
                "-protocol_whitelist",
                "file,pipe",
                "-show_entries",
                "format=duration:stream=codec_type,codec_name,width,height",
                "-of",
                "json",
                str(source),
            ],
            capture_output=True,
            check=True,
            timeout=20,
        )
        meta = json.loads(raw.stdout)
        duration = float(meta["format"]["duration"])
        if not math.isfinite(duration) or not 0 < duration <= 7200:
            raise ValueError("Unsupported video duration")
        stream = next(s for s in meta["streams"] if s["codec_type"] == "video")
        if stream["width"] * stream["height"] > 3840 * 2160:
            raise ValueError("Video resolution exceeds processing limit")
        interval = max(1.0, duration / max_frames)
        subprocess.run(  # noqa: S603
            [
                decoder,
                "-v",
                "error",
                "-nostdin",
                "-threads",
                "1",
                "-protocol_whitelist",
                "file,pipe",
                "-i",
                str(source),
                "-an",
                "-vf",
                f"fps=1/{interval},scale=320:180:force_original_aspect_ratio=decrease",
                "-frames:v",
                str(max_frames),
                str(Path(folder) / "frame-%04d.png"),
            ],
            capture_output=True,
            check=True,
            timeout=90,
        )
        frames = []
        for index, path in enumerate(sorted(Path(folder).glob("frame-*.png"))):
            with Image.open(path) as image:
                buffer = io.BytesIO()
                image.convert("RGB").save(buffer, format="PNG")
                frames.append((index * interval, buffer.getvalue()))
        if not frames:
            raise ValueError("No decodable video frames")
        return {
            "duration_seconds": duration,
            "codec": stream["codec_name"],
            "dimensions": {"width": stream["width"], "height": stream["height"]},
        }, frames
