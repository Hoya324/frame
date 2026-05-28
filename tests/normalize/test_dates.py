from datetime import date

import pytest

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
