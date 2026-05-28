"""Date parsing tolerant of Korean and English formats."""

from __future__ import annotations

import re
from datetime import date

from dateutil import parser as dateparser

_KOREAN_PATTERN = re.compile(r"(\d{4})\s*년\s*(\d{1,2})\s*월\s*(\d{1,2})\s*일")
# Compact numeric date with optional trailing dot and optional Korean weekday:
# e.g. "2026.05.22. 금" or "2026. 06. 01. 월"
_COMPACT_DATE_PATTERN = re.compile(
    r"(\d{4})\s*[.\-/]\s*(\d{1,2})\s*[.\-/]\s*(\d{1,2})\s*\.?"
    r"(?:\s*[월화수목금토일])?"
)
# A plain hyphen used as range separator must be surrounded by spaces to avoid
# splitting ISO date strings like "2026-05-19". Tilde and em/en-dashes may
# appear with or without surrounding spaces.
_RANGE_SPLIT = re.compile(r"\s*[~–—]\s*|\s+-\s+")


def parse_date(raw: str | None) -> date | None:
    if not raw:
        return None
    raw = raw.strip()
    if not raw:
        return None

    # Korean 년/월/일 pattern
    m = _KOREAN_PATTERN.search(raw)
    if m:
        try:
            return date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
        except ValueError:
            return None

    # Compact numeric date: YYYY.MM.DD. 요일 or YYYY.MM.DD
    m = _COMPACT_DATE_PATTERN.match(raw.strip())
    if m:
        try:
            return date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
        except ValueError:
            return None

    try:
        return dateparser.parse(raw, fuzzy=False).date()
    except (ValueError, OverflowError, TypeError):
        return None


def parse_date_range(raw: str | None) -> tuple[date | None, date | None]:
    if not raw:
        return None, None
    parts = _RANGE_SPLIT.split(raw, maxsplit=1)
    if len(parts) == 1:
        single = parse_date(parts[0])
        return single, single
    return parse_date(parts[0]), parse_date(parts[1])
