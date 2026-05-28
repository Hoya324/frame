from crawler.normalize.text import (
    clean_whitespace,
    normalize_name,
    normalize_address,
)


def test_clean_whitespace_collapses_runs():
    assert clean_whitespace("  hello   world  ") == "hello world"
    assert clean_whitespace("a\n\tb") == "a b"


def test_clean_whitespace_handles_zero_width_chars():
    assert clean_whitespace("a​b‌c") == "abc"


def test_normalize_name_lowercases_and_strips_punctuation():
    assert normalize_name("Kim, Joo-hyun.") == "kim joohyun"
    assert normalize_name(" 김  작가 ") == "김 작가"


def test_normalize_name_empty():
    assert normalize_name("") == ""
    assert normalize_name("   ") == ""


def test_normalize_address_strips_korean_postal_artifacts():
    assert normalize_address("(03044) 서울 종로구 자하문로 106") == "서울 종로구 자하문로 106"
    assert normalize_address("서울특별시  종로구  자하문로 106 ") == "서울 종로구 자하문로 106"
