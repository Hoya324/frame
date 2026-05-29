import json
from datetime import UTC, datetime
from pathlib import Path

from crawler.sinks.base import SheetName
from crawler.sinks.fake import FakeRepository
from crawler.sinks.json_export import (
    _bool,
    _float_or_none,
    _int_or_none,
    _split,
    _str_or_none,
    build_catalog,
    write_catalog,
)

GEN_AT = datetime(2026, 5, 30, 6, 54, tzinfo=UTC)


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


def test_build_catalog_handles_missing_venue_and_no_artists():
    repo = FakeRepository()
    repo.append_rows(SheetName.EXHIBITIONS, [{
        "id": "e9", "source": "artmap", "status": "upcoming",
        "source_url": "https://src/9", "title": "제목 없는 전시",
        "title_en": "", "description": "",
        "poster_image_url": "", "medium": "photo",
        "exhibition_type": "group", "genre_tags": "", "fee_type": "free",
        "price_min": "", "price_max": "",
        "start_date": "2026-06-20", "end_date": "", "open_hours": "",
        "artist_ids": "", "venue_id": "", "featured": "FALSE",
        "popularity_score": "",
    }])
    catalog = build_catalog(repo, generated_at=GEN_AT)
    ex = catalog["exhibitions"][0]
    assert ex["venue"] is None
    assert ex["artists"] == []
    assert ex["genre_tags"] == []
    assert ex["end_date"] is None
    assert ex["poster_image_url"] is None
    assert catalog["venues"] == []


def test_build_catalog_drops_unknown_artist_ids():
    repo = FakeRepository()
    repo.append_rows(SheetName.ARTISTS, [{"id": "a1", "name": "있는작가", "name_en": ""}])
    repo.append_rows(SheetName.EXHIBITIONS, [{
        "id": "e8", "source": "artmap", "status": "ongoing",
        "source_url": "https://src/8", "title": "T", "title_en": "",
        "description": "", "poster_image_url": "", "medium": "photo",
        "exhibition_type": "group", "genre_tags": "", "fee_type": "free",
        "price_min": "", "price_max": "", "start_date": "", "end_date": "",
        "open_hours": "", "artist_ids": "a1,ghost", "venue_id": "",
        "featured": "FALSE", "popularity_score": "",
    }])
    catalog = build_catalog(repo, generated_at=GEN_AT)
    assert catalog["exhibitions"][0]["artists"] == [{"id": "a1", "name": "있는작가"}]


def test_write_catalog_creates_parent_dirs_and_writes_json(tmp_path: Path):
    repo = _seed_repo()
    out = tmp_path / "nested" / "exhibitions.json"
    count = write_catalog(repo, str(out), generated_at=GEN_AT)

    assert count == 1
    assert out.exists()
    data = json.loads(out.read_text(encoding="utf-8"))
    assert data["generated_at"] == "2026-05-30T06:54:00+00:00"
    assert data["exhibitions"][0]["title"] == "빛과 시간의 기록"
    # Korean must not be escaped
    assert "\\u" not in out.read_text(encoding="utf-8")


def _repo_with_corrupt_numerics() -> FakeRepository:
    """Simulate gspread having numericised id/coordinate cells: a huge all-digit
    id overflowed to inf, another became a float, and a latitude is NaN."""
    repo = FakeRepository()
    repo.append_rows(SheetName.VENUES, [
        {"id": float("inf"), "name": "고은사진미술관",
         "latitude": float("nan"), "longitude": 129.0},
    ])
    repo.append_rows(SheetName.EXHIBITIONS, [
        {"id": float("inf"), "title": "부산 이바구", "venue_id": float("inf"),
         "artist_ids": "", "genre_tags": "", "featured": "FALSE"},
        {"id": 84051722820000.0, "title": "Gradually",
         "artist_ids": "", "genre_tags": "", "featured": "FALSE"},
    ])
    return repo


def test_numeric_ids_are_stringified():
    catalog = build_catalog(_repo_with_corrupt_numerics(), generated_at=GEN_AT)
    assert all(isinstance(e["id"], str) for e in catalog["exhibitions"])
    assert all(isinstance(v["id"], str) for v in catalog["venues"])


def test_nonfinite_floats_are_dropped():
    catalog = build_catalog(_repo_with_corrupt_numerics(), generated_at=GEN_AT)
    venue = catalog["venues"][0]
    assert venue["lat"] is None  # NaN dropped
    assert venue["lng"] == 129.0


def test_written_file_is_strict_valid_json(tmp_path: Path):
    out = tmp_path / "exhibitions.json"
    write_catalog(_repo_with_corrupt_numerics(), str(out), generated_at=GEN_AT)
    text = out.read_text(encoding="utf-8")
    # parse_constant fires only on non-standard Infinity/NaN tokens.
    json.loads(text, parse_constant=lambda _t: (_ for _ in ()).throw(
        AssertionError("output contains a non-standard JSON constant")))
