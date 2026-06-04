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
# "23일", "6월 3일", the Japanese "23日", or Gallery Lux's numeric "7. 2".
# We back-fill the missing month and/or year from the already-parsed start.
# Group 1 = optional month, group 2 = day. Handles 월/月 (CJK) and bare
# numerics ("6.3", "23").
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
    # An explicit four-digit year often appears only in the END half, e.g.
    # "May 10 – Jul 3, 2026" or K.O.N.G Gallery's "Oct 15 ~ 30, 2021". Capture
    # it once so it can back-fill both the yearless start and a day-only end.
    right_year_match = _FOUR_DIGIT_YEAR.search(right_raw)
    # If the left half lacks an explicit year but the right half has one,
    # re-parse the left with the right's year appended. Without this, dateutil
    # assigns *today's* year to the start date — correct-by-luck only when
    # today happens to match the right-side year. This must fire even when the
    # end half itself didn't parse to a full date (KONG's "30, 2021" is a
    # day + year, with no month, so `right` is None there).
    if right_year_match and not _FOUR_DIGIT_YEAR.search(left_raw):
        patched_left = parse_date(f"{left_raw.strip()}, {right_year_match.group(1)}")
        if patched_left is not None:
            left = patched_left

    # Resolve the end half's year/month from the start when the end half omits
    # them. Two variants of the same bug, both of which otherwise let dateutil
    # stamp *today's* year onto the end:
    #   (a) No explicit year in the end half — e.g. Gallery Lux's
    #       "2021. 6. 4 - 7. 2" (end "7. 2") or KOBA's "...~ 23일" (day only).
    #       dateutil may even parse "7. 2" to a current-year date, so we must
    #       re-derive regardless of whether `right` already parsed: the year
    #       comes from the start, the month from the end when present (else the
    #       start), and a backwards span rolls into the next year (Dec → Jan).
    #   (b) An explicit year IS present but the end couldn't be parsed as a full
    #       date — KONG's "30, 2021" (day + year, no month). Use that year and
    #       back-fill the month from the start.
    if left is not None and right_year_match is None:
        m = _ABBREV_END.match(right_raw.strip())
        if m:
            month = int(m.group(1)) if m.group(1) else left.month
            day = int(m.group(2))
            try:
                candidate = date(left.year, month, day)
                if candidate < left:  # span rolls into the next year (Dec → Jan)
                    candidate = date(left.year + 1, month, day)
                right = candidate
            except ValueError:
                pass  # keep whatever `right` parsed to
    elif left is not None and right is None:
        end_core = _FOUR_DIGIT_YEAR.sub("", right_raw).strip(" ,.")
        m = _ABBREV_END.match(end_core)
        if m:
            month = int(m.group(1)) if m.group(1) else left.month
            day = int(m.group(2))
            try:
                right = date(int(right_year_match.group(1)), month, day)
            except ValueError:
                pass
    return left, right
