"""Domain services for Phase 11 media analysis, frame sampling,
equipment detection, and floor plan reconciliation.
"""

from __future__ import annotations

import io
from typing import Any

from PIL import Image, ImageDraw

from workbench.modules.media_analysis.contracts import (
    VideoRole,
    VideoRolePolicy,
)


def compute_average_hash(img: Image.Image, hash_size: int = 8) -> str:
    """Compute 64-bit Average Hash (aHash) for perceptual comparison."""
    resized = img.convert("L").resize((hash_size, hash_size), Image.Resampling.LANCZOS)
    getter = getattr(resized, "get_flattened_data", resized.getdata)
    pixels = list(getter())
    avg = sum(pixels) / len(pixels) if pixels else 0
    bits = "".join("1" if p >= avg else "0" for p in pixels)
    # Convert 64-bit binary string to 16-hex characters
    hex_str = f"{int(bits, 2):016x}" if bits else "0" * 16
    return hex_str


def compute_difference_hash(img: Image.Image, hash_size: int = 8) -> str:
    """Compute 64-bit Difference Hash (dHash) tracking horizontal luminance gradients."""
    resized = img.convert("L").resize((hash_size + 1, hash_size), Image.Resampling.LANCZOS)
    getter = getattr(resized, "get_flattened_data", resized.getdata)
    pixels = list(getter())
    width = hash_size + 1
    bits = []
    for y in range(hash_size):
        for x in range(hash_size):
            left = pixels[y * width + x]
            right = pixels[y * width + x + 1]
            bits.append("1" if right > left else "0")
    bits_str = "".join(bits)
    hex_str = f"{int(bits_str, 2):016x}" if bits_str else "0" * 16
    return hex_str


def hamming_distance(hex1: str, hex2: str) -> int:
    """Calculate Hamming bit distance between two hexadecimal hashes."""
    try:
        val1 = int(hex1, 16)
        val2 = int(hex2, 16)
        xor_val = val1 ^ val2
        return bin(xor_val).count("1")
    except ValueError:
        return 64


def extract_gps_and_exif(img: Image.Image) -> tuple[bool, dict[str, Any] | None, dict[str, Any]]:
    """Extract GPS coordinates and EXIF tags from image if present.

    Missing GPS or missing EXIF is NEVER an error or compliance failure;
    it is recorded honestly as unavailable metadata.
    """
    exif = img.getexif()
    if not exif:
        return False, None, {}

    raw_exif: dict[str, Any] = {}
    for tag_id, value in exif.items():
        try:
            raw_exif[str(tag_id)] = str(value)
        except Exception:  # noqa: S112
            continue

    gps_info = exif.get_ifd(0x8825)
    if not gps_info:
        return False, None, raw_exif

    def to_decimal(coords: Any, ref: str) -> float | None:
        try:
            if isinstance(coords, tuple | list) and len(coords) == 3:
                d = float(coords[0])
                m = float(coords[1])
                s = float(coords[2])
                dec = d + (m / 60.0) + (s / 3600.0)
                if ref in ("S", "W"):
                    dec = -dec
                return round(dec, 6)
        except Exception:
            return None
        return None

    lat_ref = gps_info.get(1, "N")
    lat_data = gps_info.get(2)
    lon_ref = gps_info.get(3, "E")
    lon_data = gps_info.get(4)
    alt_data = gps_info.get(6)

    latitude = to_decimal(lat_data, lat_ref) if lat_data else None
    longitude = to_decimal(lon_data, lon_ref) if lon_data else None
    altitude = float(alt_data) if alt_data is not None else None

    if latitude is not None and longitude is not None:
        return (
            True,
            {
                "latitude": latitude,
                "longitude": longitude,
                "altitude": altitude,
            },
            raw_exif,
        )

    return False, None, raw_exif


def validate_video_duration_policy(
    video_role_str: str,
    duration_seconds: float,
) -> dict[str, Any]:
    """Validate video duration against role-specific requirements.

    Website disclosure (1-2 min) and contextual EVC walkthroughs (longer)
    must NOT share one global duration constant!
    """
    try:
        role = VideoRole(video_role_str)
    except ValueError:
        role = VideoRole.NONE

    policy = VideoRolePolicy.get_policy(role)
    is_compliant = policy.min_seconds <= duration_seconds <= policy.max_seconds

    discrepancy = None
    if not is_compliant:
        if duration_seconds < policy.min_seconds:
            discrepancy = (
                f"Video duration ({duration_seconds:.1f}s) falls below minimum required "
                f"duration ({policy.min_seconds:.1f}s) for role {role.value} "
                f"({policy.description})."
            )
        else:
            discrepancy = (
                f"Video duration ({duration_seconds:.1f}s) exceeds maximum allowed "
                f"duration ({policy.max_seconds:.1f}s) for role {role.value} "
                f"({policy.description})."
            )

    return {
        "video_role": role.value,
        "duration_seconds": round(duration_seconds, 2),
        "compliant": is_compliant,
        "expected_min_seconds": policy.min_seconds,
        "expected_max_seconds": policy.max_seconds,
        "policy_description": policy.description,
        "discrepancy": discrepancy,
    }


def sample_video_frames(
    duration_seconds: float,
    max_frames: int = 180,
    interval_seconds: float = 10.0,
) -> list[tuple[int, float]]:
    """Generate deterministic timestamps for frame sampling.

    Bounded sampler: one frame every 10 seconds, up to max_frames.
    """
    frames: list[tuple[int, float]] = []
    current_time = 0.0
    index = 0
    while current_time <= duration_seconds and index < max_frames:
        frames.append((index, round(current_time, 2)))
        current_time += interval_seconds
        index += 1
    if not frames and duration_seconds > 0:
        frames.append((0, 0.0))
    return frames


def generate_contact_sheet(
    frames: list[tuple[float, Image.Image]],
    cols: int = 3,
    tile_width: int = 160,
    tile_height: int = 90,
) -> bytes:
    """Render a composite contact sheet thumbnail grid of sampled frames."""
    if not frames:
        blank = Image.new("RGB", (tile_width, tile_height), color=(30, 30, 30))
        out = io.BytesIO()
        blank.save(out, format="PNG")
        return out.getvalue()

    count = len(frames)
    rows = (count + cols - 1) // cols
    sheet_w = cols * tile_width
    sheet_h = rows * tile_height

    sheet = Image.new("RGB", (sheet_w, sheet_h), color=(20, 20, 20))
    draw = ImageDraw.Draw(sheet)

    for i, (ts, frame_img) in enumerate(frames):
        c = i % cols
        r = i // cols
        x = c * tile_width
        y = r * tile_height
        resized = frame_img.convert("RGB").resize(
            (tile_width, tile_height), Image.Resampling.BILINEAR
        )
        sheet.paste(resized, (x, y))
        # Draw timestamp badge
        mins = int(ts // 60)
        secs = int(ts % 60)
        ts_text = f"{mins:02d}:{secs:02d}"
        draw.rectangle([x + 4, y + 4, x + 50, y + 18], fill=(0, 0, 0, 180))
        draw.text((x + 8, y + 4), ts_text, fill=(255, 255, 255))

    out = io.BytesIO()
    sheet.save(out, format="PNG")
    return out.getvalue()
