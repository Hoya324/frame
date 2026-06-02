"""Date parsing tolerant of Korean and English formats."""

from __future__ import annotations

import re
from datetime import date

from dateutil import parser as dateparser

_KOREAN_PATTERN = re.compile(r"(\d{4})\s*년\s*(\d{1,2})\s*월\s*(\d{1,2})\s*일")
# Japanese 年/月/日 — different codepoints from the Korean variant above.
_JAPANESE_PATTERN = re.compile(r"(\d{4})\s*年\s*(\d{1,2})\s*月\s*(\d{1,2})\s*日")
# Compact numeric date with optional trailing dot and optional Korean weekday:
# e.g. "2026.05.22. 금" or "2026. 06. 01. 월"
_COMPACT_DATE_PATTERN = re.compile(
    r"(\d{4})\s*[.\-/]\s*(\d{1,2})\s*[.\-/]\s*(\d{1,2})\s*\.?"
    r"(?:\s*[월화수목금토일])?"
)
# Range separator: tilde, en/em-dash, JP wave-dash 〜 (U+301C), fullwidth
# tilde ～ (U+FF5E), fullwidth hyphen － (U+FF0D), or a space-padded ASCII
# hyphen. A plain ASCII hyphen without surrounding spaces would split ISO
# dates like "2026-05-19".
_RANGE_SPLIT = re.compile(r"\s*[~–—〜～－]\s*|\s+-\s+")
# Used to detect whether a half of a date range carries its own explicit
# four-digit year. Tokyo Art Beat renders strings like "May 10 – Jul 3, 2026"
# where only the right half has the year; without back-filling from the right
# half, dateutil silently defaults the left half to today's year.
_FOUR_DIGIT_YEAR = re.compile(r"\b(\d{4})\b")
# An abbreviated end half that carries no four-digit year, e.g. KOBA's
# "23일", "6월 3일", or the Japanese "23日". We back-fill the missing month
# and/or year from the already-parsed start date. Group 1 = optional month,
# group 2 = day. Handles 월/月 (CJK) and bare numerics ("6.3", "23").
_ABBREV_END = re.compile(
    r"^\s*(?:(\d{1,2})\s*[월月.\-/]\s*)?(\d{1,2})\s*[일日]?\s*"
    r"(?:[（(]\s*[월화수목금토일月火水木金土日]\s*[）)])?\s*$"
)


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

    # Japanese 年/月/日 pattern (codepoints differ from Korean)
    m = _JAPANESE_PATTERN.search(raw)
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
    left_raw, right_raw = parts[0], parts[1]
    left = parse_date(left_raw)
    right = parse_date(right_raw)
    # If the left half lacks an explicit year but the right half has one,
    # re-parse the left with the right's year appended. Without this,
    # "May 10 – Jul 3, 2026" would assign today's year to the start date —
    # correct-by-luck only when today's year matches the right-side year.
    if right is not None and not _FOUR_DIGIT_YEAR.search(left_raw):
        right_year_match = _FOUR_DIGIT_YEAR.search(right_raw)
        if right_year_match:
            patched = f"{left_raw.strip()}, {right_year_match.group(1)}"
            patched_left = parse_date(patched)
            if patched_left is not None:
                left = patched_left
    # Symmetric case: the end half omits the year (and maybe the month), e.g.
    # KOBA's "2025년 5월 20일 ~ 23일". Back-fill year/month from the start so the
    # show gets a real end date instead of staying "ongoing" forever.
    if left is not None and right is None:
        m = _ABBREV_END.match(right_raw)
        if m:
            month = int(m.group(1)) if m.group(1) else left.month
            day = int(m.group(2))
            try:
                right = date(left.year, month, day)
                if right < left:  # span rolls into the next year (Dec → Jan)
                    right = date(left.year + 1, month, day)
            except ValueError:
                right = None
    return left, right
