"""Regulatory value normalization: dates with ambiguity, units with Decimal, and NFKC identities."""

from __future__ import annotations

import re
import unicodedata
from datetime import datetime
from decimal import ROUND_HALF_UP, Decimal
from typing import Any

# Conversion factors to canonical units using exact Decimal representations
SQ_METERS_PER_ACRE = Decimal("4046.8564224")
SQ_METERS_PER_HECTARE = Decimal("10000.0")
SQ_METERS_PER_SQ_FOOT = Decimal("0.09290304")
MBPS_PER_GBPS = Decimal("1000.0")
MBPS_PER_KBPS = Decimal("0.001")


def normalize_date(raw_text: str) -> dict[str, Any]:
    """Normalize date string to ISO-8601, explicitly preserving ambiguity markers."""
    text = raw_text.strip()

    # 1. ISO format: YYYY-MM-DD
    iso_match = re.search(r"\b(\d{4})-(\d{1,2})-(\d{1,2})\b", text)
    if iso_match:
        y, m, d = int(iso_match.group(1)), int(iso_match.group(2)), int(iso_match.group(3))
        dt = datetime(y, m, d)
        return {
            "iso_date": dt.strftime("%Y-%m-%d"),
            "ambiguous": False,
            "format_inferred": "YYYY-MM-DD",
            "year": y,
            "month": m,
            "day": d,
        }

    # 2. Slashed or dotted format: DD/MM/YYYY or MM/DD/YYYY
    slash_match = re.search(r"\b(\d{1,2})[/.-](\d{1,2})[/.-](\d{4})\b", text)
    if slash_match:
        part1 = int(slash_match.group(1))
        part2 = int(slash_match.group(2))
        year = int(slash_match.group(3))

        if part1 > 12 and part2 <= 12:
            # Unambiguously DD/MM/YYYY
            dt = datetime(year, part2, part1)
            return {
                "iso_date": dt.strftime("%Y-%m-%d"),
                "ambiguous": False,
                "format_inferred": "DD/MM/YYYY",
                "year": year,
                "month": part2,
                "day": part1,
            }
        elif part2 > 12 and part1 <= 12:
            # Unambiguously MM/DD/YYYY
            dt = datetime(year, part1, part2)
            return {
                "iso_date": dt.strftime("%Y-%m-%d"),
                "ambiguous": False,
                "format_inferred": "MM/DD/YYYY",
                "year": year,
                "month": part1,
                "day": part2,
            }
        elif part1 <= 12 and part2 <= 12 and part1 != part2:
            # Ambiguous! In India, DD/MM/YYYY is standard, but MM/DD/YYYY is common in US imports.
            dt_primary = datetime(year, part2, part1)  # DD/MM/YYYY
            dt_alt = datetime(year, part1, part2)  # MM/DD/YYYY
            return {
                "iso_date": dt_primary.strftime("%Y-%m-%d"),
                "ambiguous": True,
                "alternate_iso_date": dt_alt.strftime("%Y-%m-%d"),
                "format_inferred": "DD/MM/YYYY",
                "format_alternate": "MM/DD/YYYY",
                "ambiguity_reason": f"Values {part1} and {part2} can both represent day or month",
                "year": year,
                "month": part2,
                "day": part1,
            }
        else:
            # part1 == part2 (e.g. 05/05/2024)
            dt = datetime(year, part1, part2)
            return {
                "iso_date": dt.strftime("%Y-%m-%d"),
                "ambiguous": False,
                "format_inferred": "DD/MM/YYYY",
                "year": year,
                "month": part1,
                "day": part2,
            }

    # 3. Textual month format: "15 August 2024" or "August 15, 2024"
    for fmt in ("%d %B %Y", "%d %b %Y", "%B %d, %Y", "%b %d, %Y", "%B %d %Y"):
        try:
            cleaned = re.sub(r"(\d+)(st|nd|rd|th)", r"\1", text)
            parsed = datetime.strptime(cleaned, fmt)
            return {
                "iso_date": parsed.strftime("%Y-%m-%d"),
                "ambiguous": False,
                "format_inferred": fmt,
                "year": parsed.year,
                "month": parsed.month,
                "day": parsed.day,
            }
        except ValueError:
            pass

    # 4. Academic year pattern: e.g. "2024-25" or "2024-2025"
    acad_match = re.search(r"\b(20\d{2})[-/](20\d{2}|\d{2})\b", text)
    if acad_match:
        start_yr = int(acad_match.group(1))
        end_part = acad_match.group(2)
        end_yr = int(end_part) if len(end_part) == 4 else int(str(start_yr)[:2] + end_part)
        return {
            "iso_date": f"{start_yr}-07-01",
            "academic_year": f"{start_yr}-{end_yr}",
            "ambiguous": False,
            "format_inferred": "ACADEMIC_YEAR",
            "year": start_yr,
        }

    return {
        "raw_text": raw_text,
        "iso_date": None,
        "ambiguous": True,
        "ambiguity_reason": "Unrecognized date format",
    }


def normalize_unit(raw_text: str, default_unit: str | None = None) -> dict[str, Any]:
    """Normalize numeric values and units using exact Decimal representations
    with conversion traces.
    """
    text = raw_text.strip()

    # Extract first numeric token (supports decimals, commas like 1,000.50)
    num_match = re.search(r"[-+]?\d+(?:,\d{3})*(?:\.\d+)?", text)
    if not num_match:
        return {
            "raw_text": raw_text,
            "decimal_value": None,
            "unit": None,
            "canonical_value": None,
            "canonical_unit": None,
        }

    num_str = num_match.group(0).replace(",", "")
    dec_val = Decimal(num_str)

    lower_text = text.lower()

    # 1. Land / Area Units
    if "acre" in lower_text:
        unit = "ACRES"
        canonical_val = (dec_val * SQ_METERS_PER_ACRE).quantize(
            Decimal("0.01"), rounding=ROUND_HALF_UP
        )
        canonical_unit = "SQ_METERS"
        trace = f"{dec_val} * {SQ_METERS_PER_ACRE} = {canonical_val}"
    elif "hectare" in lower_text or "ha" in lower_text.split():
        unit = "HECTARES"
        canonical_val = (dec_val * SQ_METERS_PER_HECTARE).quantize(
            Decimal("0.01"), rounding=ROUND_HALF_UP
        )
        canonical_unit = "SQ_METERS"
        trace = f"{dec_val} * {SQ_METERS_PER_HECTARE} = {canonical_val}"
    elif "sq" in lower_text and (
        "meter" in lower_text or "metre" in lower_text or "m" in lower_text
    ):
        unit = "SQ_METERS"
        canonical_val = dec_val
        canonical_unit = "SQ_METERS"
        trace = f"{dec_val} (identity)"
    elif "sq" in lower_text and (
        "ft" in lower_text or "feet" in lower_text or "foot" in lower_text
    ):
        unit = "SQ_FEET"
        canonical_val = (dec_val * SQ_METERS_PER_SQ_FOOT).quantize(
            Decimal("0.01"), rounding=ROUND_HALF_UP
        )
        canonical_unit = "SQ_METERS"
        trace = f"{dec_val} * {SQ_METERS_PER_SQ_FOOT} = {canonical_val}"

    # 2. Bandwidth / Network Units
    elif "gbps" in lower_text:
        unit = "GBPS"
        canonical_val = (dec_val * MBPS_PER_GBPS).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        canonical_unit = "MBPS"
        trace = f"{dec_val} * {MBPS_PER_GBPS} = {canonical_val}"
    elif "mbps" in lower_text:
        unit = "MBPS"
        canonical_val = dec_val
        canonical_unit = "MBPS"
        trace = f"{dec_val} (identity)"
    elif "kbps" in lower_text:
        unit = "KBPS"
        canonical_val = (dec_val * MBPS_PER_KBPS).quantize(Decimal("0.001"), rounding=ROUND_HALF_UP)
        canonical_unit = "MBPS"
        trace = f"{dec_val} * {MBPS_PER_KBPS} = {canonical_val}"

    # 3. Discrete Counts (Intake, Seats, Faculty, Rooms)
    elif "seat" in lower_text or "intake" in lower_text or "student" in lower_text:
        unit = "SEATS"
        canonical_val = dec_val
        canonical_unit = "SEATS"
        trace = f"{dec_val} (count)"
    elif "faculty" in lower_text or "teacher" in lower_text:
        unit = "COUNT"
        canonical_val = dec_val
        canonical_unit = "COUNT"
        trace = f"{dec_val} (count)"
    else:
        unit = default_unit or "UNIT"
        canonical_val = dec_val
        canonical_unit = default_unit or "UNIT"
        trace = f"{dec_val} (unspecified unit)"

    return {
        "raw_text": raw_text,
        "decimal_value": str(dec_val),
        "unit": unit,
        "canonical_value": str(canonical_val),
        "canonical_unit": canonical_unit,
        "conversion_trace": trace,
    }


def normalize_identity(raw_text: str) -> str:
    """Normalize institutional, room, or subject identity strings using
    Unicode NFKC normalization.
    """
    if not raw_text:
        return ""

    # 1. Unicode NFKC normalization
    nfkc = unicodedata.normalize("NFKC", raw_text)

    # 2. Collapse internal whitespace and strip leading/trailing
    collapsed = " ".join(nfkc.strip().split())

    # 3. Standardize common institutional punctuation and uppercase
    canonical = collapsed.upper()
    return canonical
