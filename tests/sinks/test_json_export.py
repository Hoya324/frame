from crawler.sinks.json_export import (
    _bool,
    _float_or_none,
    _int_or_none,
    _split,
    _str_or_none,
)


def test_split_returns_list_or_empty():
    assert _split("a,b,c") == ["a", "b", "c"]
    assert _split("") == []
    assert _split("  a , b ") == ["a", "b"]


def test_str_or_none():
    assert _str_or_none("x") == "x"
    assert _str_or_none("") is None
    assert _str_or_none(None) is None


def test_int_or_none_accepts_str_and_int():
    assert _int_or_none(10000) == 10000
    assert _int_or_none("10000") == 10000
    assert _int_or_none("") is None
    assert _int_or_none(None) is None


def test_float_or_none_accepts_str_and_float():
    assert _float_or_none(37.58) == 37.58
    assert _float_or_none("126.98") == 126.98
    assert _float_or_none("") is None


def test_bool_reads_sheet_truthiness():
    assert _bool("TRUE") is True
    assert _bool(True) is True
    assert _bool("FALSE") is False
    assert _bool("") is False
    assert _bool(None) is False
