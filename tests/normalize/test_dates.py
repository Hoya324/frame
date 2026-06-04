from datetime import date

import pytest
from freezegun import freeze_time

from crawler.normalize.dates import parse_date, parse_date_range


@pytest.mark.parametrize(
    "raw, expected",
    [
        ("2026.05.19", date(2026, 5, 19)),
        ("2026-05-19", date(2026, 5, 19)),
        ("2026/05/19", date(2026, 5, 19)),
        ("2026년 5월 19일", date(2026, 5, 19)),
        ("May 19, 2026", date(2026, 5, 19)),
        ("19 May 2026", date(2026, 5, 19)),
    ],
)
def test_parse_date_formats(raw: str, expected: date):
    assert parse_date(raw) == expected


def test_parse_date_returns_none_on_garbage():
    assert parse_date("미정") is None
    assert parse_date("") is None
    assert parse_date(None) is None


def test_parse_date_range_with_tilde():
    start, end = parse_date_range("2026.05.19 ~ 2026.10.25")
    assert start == date(2026, 5, 19) and end == date(2026, 10, 25)


def test_parse_date_range_with_dash():
    start, end = parse_date_range("2026-05-19 - 2026-10-25")
    assert start == date(2026, 5, 19) and end == date(2026, 10, 25)


def test_parse_date_range_partial_returns_what_it_can():
    start, end = parse_date_range("2026.05.19 ~ 미정")
    assert start == date(2026, 5, 19) and end is None


@pytest.mark.parametrize(
    "raw, expected_start, expected_end",
    [
        # Museum Hanmi compact format: YYYY.MM.DD. 요일
        (
            "2026.05.22. 금 ~ 2026.09.30. 수",
            date(2026, 5, 22),
            date(2026, 9, 30),
        ),
        # Museum Hanmi spaced format: YYYY. MM. DD. 요일
        (
            "2026. 06. 01. 월 ~ 2026. 07. 15. 화",
            date(2026, 6, 1),
            date(2026, 7, 15),
        ),
        (
            "2026.03.27. 금 ~ 2026.07.19. 일",
            date(2026, 3, 27),
            date(2026, 7, 19),
        ),
    ],
)
def test_parse_date_range_korean_weekday_suffix(
    raw: str, expected_start: date, expected_end: date
):
    start, end = parse_date_range(raw)
    assert start == expected_start, f"start mismatch: {start!r}"
    assert end == expected_end, f"end mismatch: {end!r}"


def test_parse_date_japanese_year_month_day():
    assert parse_date("2026年5月10日") == date(2026, 5, 10)
    assert parse_date("2026年12月3日") == date(2026, 12, 3)


def test_parse_date_range_japanese():
    s, e = parse_date_range("2026年5月10日 ～ 2026年7月3日")
    assert s == date(2026, 5, 10)
    assert e == date(2026, 7, 3)


def test_parse_date_range_japanese_compact_separator():
    """Japanese sites also use 〜 (U+301C) and － (full-width hyphen)."""
    s, e = parse_date_range("2026/5/10〜2026/7/3")
    assert s == date(2026, 5, 10)
    assert e == date(2026, 7, 3)


def test_parse_date_range_english_with_year_at_end():
    """Tokyo Art Beat sometimes renders 'May 10 – Jul 3, 2026'."""
    s, e = parse_date_range("May 10 – Jul 3, 2026")
    assert s == date(2026, 5, 10)
    assert e == date(2026, 7, 3)


@freeze_time("2030-01-15")
def test_parse_date_range_english_year_at_end_uses_explicit_right_year():
    """If today is 2030 but the string says ',2026', the start must be 2026."""
    s, e = parse_date_range("May 10 – Jul 3, 2026")
    assert s == date(2026, 5, 10), f"start: got {s}, expected 2026-05-10"
    assert e == date(2026, 7, 3), f"end: got {e}, expected 2026-07-03"


def test_parse_date_korean_still_works():
    """Regression guard: Korean patterns must keep parsing identically."""
    assert parse_date("2026년 5월 10일") == date(2026, 5, 10)
    s, e = parse_date_range("2026.05.10 ~ 2026.07.03")
    assert s == date(2026, 5, 10)
    assert e == date(2026, 7, 3)


@pytest.mark.parametrize(
    "raw, expected_start, expected_end",
    [
        # KOBA: "YYYY년 M월 D일(요일) ~ D일(요일)" — end carries only the day,
        # so year+month must be back-filled from the start.
        (
            "2025년 5월 20일(화) ~ 23일(금)",
            date(2025, 5, 20),
            date(2025, 5, 23),
        ),
        # End spans into a new month — back-fill only the year.
        (
            "2025년 5월 20일 ~ 6월 3일",
            date(2025, 5, 20),
            date(2025, 6, 3),
        ),
        # Japanese 年/月/日 with a day-only end.
        (
            "2025年5月20日 ～ 23日",
            date(2025, 5, 20),
            date(2025, 5, 23),
        ),
    ],
)
def test_parse_date_range_back_fills_abbreviated_end(
    raw: str, expected_start: date, expected_end: date
):
    start, end = parse_date_range(raw)
    assert start == expected_start, f"start: {start!r}"
    assert end == expected_end, f"end: {end!r}"


@freeze_time("2026-06-05")
@pytest.mark.parametrize(
    "raw",
    [
        # K.O.N.G Gallery poster format: English month-name start, end half is
        # day-only followed by the year ("Oct 15 ~ 30 , 2021"). The year lives
        # only on the right and must back-fill the start (NOT default to today's
        # year), and the day-only end must be recovered with that same year.
        "Oct 15 ~ 30 , 2021",
        "Oct 15 ~ 30, 2021",
    ],
)
def test_parse_date_range_english_month_start_day_only_end_with_year(raw: str):
    s, e = parse_date_range(raw)
    assert s == date(2021, 10, 15), f"start: got {s}, expected 2021-10-15"
    assert e == date(2021, 10, 30), f"end: got {e}, expected 2021-10-30"
