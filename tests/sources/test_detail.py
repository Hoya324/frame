from crawler.sources._detail import extract_date_range


def test_dotted_tilde():
    assert extract_date_range("전시 2025.8.1~8.30 입니다") == "2025.08.01~2025.08.30"


def test_padded_with_trailing_dot():
    assert extract_date_range("기간 2025.04.21.~05.06") == "2025.04.21~2025.05.06"


def test_end_is_day_only():
    assert extract_date_range("2024.11.20~29") == "2024.11.20~2024.11.29"


def test_kr_weekday_parens_endash():
    text = "전시 일정 : 2025. 1. 16 (목) – 1. 25 (토) 전시 장소"
    assert extract_date_range(text) == "2025.01.16~2025.01.25"


def test_jp_weekday_parens_fullwidth_dash():
    # PGI-style: JP weekday in parens, full-width hyphen separator.
    text = "原直久 「柘榴」 2026.5.22(金) － 7.11(土)"
    assert extract_date_range(text) == "2026.05.22~2026.07.11"


def test_picks_first_when_multiple():
    text = "2025.8.1~8.30 1부 2025.8.1~8.10 2부 2025.8.11~8.20"
    assert extract_date_range(text) == "2025.08.01~2025.08.30"


def test_none_when_absent():
    assert extract_date_range("작가 소개만 있고 날짜는 없음") is None
