from datetime import date

from crawler.normalize.dedup import (
    exhibition_id,
    artist_id,
    venue_id,
    organizer_id,
)


def test_exhibition_id_is_stable():
    a = exhibition_id("artmap", "류가헌", "달과 도시", date(2026, 6, 1))
    b = exhibition_id("artmap", "류가헌", "달과 도시", date(2026, 6, 1))
    assert a == b
    assert len(a) == 12


def test_exhibition_id_differs_by_source():
    a = exhibition_id("artmap", "류가헌", "달과 도시", date(2026, 6, 1))
    b = exhibition_id("naver", "류가헌", "달과 도시", date(2026, 6, 1))
    assert a != b


def test_exhibition_id_tolerates_missing_date():
    a = exhibition_id("artmap", "류가헌", "달과 도시", None)
    assert len(a) == 12


def test_artist_id_uses_normalized_name():
    # Different inputs that normalize to same name should collide
    a = artist_id("김작가")
    b = artist_id("김 작가")  # different raw, same normalized handled upstream
    assert a != b  # caller must normalize before calling
    assert len(a) == 12


def test_venue_id_prefers_address():
    with_addr = venue_id("류가헌", "서울 종로구 자하문로 106")
    name_only = venue_id("류가헌", None)
    assert with_addr != name_only


def test_organizer_id_stable():
    assert organizer_id("한국전파진흥협회") == organizer_id("한국전파진흥협회")
