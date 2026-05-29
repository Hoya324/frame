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


from datetime import UTC, datetime

from crawler.sinks.base import SheetName
from crawler.sinks.fake import FakeRepository
from crawler.sinks.json_export import build_catalog

GEN_AT = datetime(2026, 5, 30, 6, 54, tzinfo=UTC)


def _seed_repo() -> FakeRepository:
    repo = FakeRepository()
    repo.append_rows(SheetName.VENUES, [{
        "id": "v1", "name": "한미사진미술관", "name_en": "MoPS",
        "venue_type": "museum", "region": "서울", "district": "삼청",
        "address": "삼청로 9", "country": "KR",
        "latitude": 37.58, "longitude": 126.98, "website": "",
        "open_hours_default": "",
    }])
    repo.append_rows(SheetName.ARTISTS, [
        {"id": "a1", "name": "김작가", "name_en": ""},
        {"id": "a2", "name": "이작가", "name_en": "Lee"},
    ])
    repo.append_rows(SheetName.EXHIBITIONS, [{
        "id": "e1", "source": "artmap", "status": "ongoing",
        "source_url": "https://src/1", "title": "빛과 시간의 기록",
        "title_en": "", "description": "설명",
        "poster_image_url": "https://example.com/p.jpg",
        "medium": "photo", "exhibition_type": "solo",
        "genre_tags": "documentary,portrait", "fee_type": "free",
        "price_min": "", "price_max": "",
        "start_date": "2026-05-30", "end_date": "2026-07-20",
        "open_hours": "10:00–18:00", "artist_ids": "a1,a2", "venue_id": "v1",
        "featured": "TRUE", "popularity_score": "",
    }])
    return repo


def test_build_catalog_embeds_venue_and_artists():
    catalog = build_catalog(_seed_repo(), generated_at=GEN_AT)

    assert catalog["generated_at"] == "2026-05-30T06:54:00+00:00"
    assert len(catalog["exhibitions"]) == 1

    ex = catalog["exhibitions"][0]
    assert ex["id"] == "e1"
    assert ex["title"] == "빛과 시간의 기록"
    assert ex["title_en"] is None
    assert ex["genre_tags"] == ["documentary", "portrait"]
    assert ex["fee_type"] == "free"
    assert ex["price_min"] is None
    assert ex["featured"] is True
    assert ex["status"] == "ongoing"
    assert ex["venue"] == {
        "id": "v1", "name": "한미사진미술관", "region": "서울",
        "district": "삼청", "lat": 37.58, "lng": 126.98,
    }
    assert ex["artists"] == [
        {"id": "a1", "name": "김작가"},
        {"id": "a2", "name": "이작가"},
    ]


def test_build_catalog_lists_full_venues_and_artists():
    catalog = build_catalog(_seed_repo(), generated_at=GEN_AT)
    assert catalog["venues"][0]["lat"] == 37.58
    assert catalog["venues"][0]["website"] is None
    assert catalog["artists"][1] == {"id": "a2", "name": "이작가", "name_en": "Lee"}
