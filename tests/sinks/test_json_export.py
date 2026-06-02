import json
from datetime import UTC, datetime
from pathlib import Path

from crawler.sinks.base import SheetName
from crawler.sinks.fake import FakeRepository
from crawler.sinks.json_export import (
    _artist_full,
    _bool,
    _exhibition_json,
    _float_or_none,
    _int_or_none,
    _split,
    _str_or_none,
    _venue_full,
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
    assert ex["source"] == "artmap"
    assert ex["title"] == "빛과 시간의 기록"
    assert "title_en" not in ex
    assert ex["tr"] == {}
    assert ex["lang"] is None
    assert ex["genre_tags"] == ["documentary", "portrait"]
    assert ex["fee_type"] == "free"
    assert ex["price_min"] is None
    assert ex["featured"] is True
    assert ex["status"] == "ongoing"
    assert ex["venue"] == {
        "id": "v1", "name": "한미사진미술관", "lang": None, "tr": {},
        "region": "서울", "district": "삼청", "lat": 37.58, "lng": 126.98,
    }
    assert ex["artists"] == [
        {"id": "a1", "name": "김작가", "lang": None, "tr": {}},
        {"id": "a2", "name": "이작가", "lang": None, "tr": {}},
    ]


def test_build_catalog_lists_full_venues_and_artists():
    catalog = build_catalog(_seed_repo(), generated_at=GEN_AT)
    assert catalog["venues"][0]["lat"] == 37.58
    assert catalog["venues"][0]["website"] is None
    assert catalog["artists"][1] == {"id": "a2", "name": "이작가", "lang": None, "tr": {}}


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


def test_build_catalog_collapses_duplicate_exhibition_ids():
    """Rows that predate the upsert dedupe fix can carry the same id many
    times (goeun's '부산 이바구' x7). The export must ship each id once."""
    repo = FakeRepository()
    dup = {
        "id": "e1", "source": "goeun", "status": "past",
        "source_url": "https://src/1", "title": "부산 이바구", "title_en": "",
        "description": "", "poster_image_url": "", "medium": "photo",
        "exhibition_type": "group", "genre_tags": "", "fee_type": "free",
        "price_min": "", "price_max": "", "start_date": "2022-04-30",
        "end_date": "2022-08-21", "open_hours": "", "artist_ids": "",
        "venue_id": "", "featured": "FALSE", "popularity_score": "",
    }
    repo.append_rows(SheetName.EXHIBITIONS, [dict(dup) for _ in range(7)])
    catalog = build_catalog(repo, generated_at=GEN_AT)
    assert len(catalog["exhibitions"]) == 1
    assert catalog["exhibitions"][0]["id"] == "e1"


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
    assert catalog["exhibitions"][0]["artists"] == [
        {"id": "a1", "name": "있는작가", "lang": None, "tr": {}}
    ]


def _repo_mixed_relevance() -> FakeRepository:
    repo = FakeRepository()
    repo.append_rows(SheetName.VENUES, [
        {"id": "v_keep", "name": "사진갤러리", "latitude": 37.5, "longitude": 127.0},
        {"id": "v_drop", "name": "회화갤러리", "latitude": 37.6, "longitude": 127.1},
    ])
    repo.append_rows(SheetName.ARTISTS, [
        {"id": "a_keep", "name": "사진작가", "name_en": ""},
        {"id": "a_drop", "name": "회화작가", "name_en": ""},
    ])
    base = {
        "title_en": "", "description": "", "poster_image_url": "",
        "exhibition_type": "solo", "genre_tags": "", "fee_type": "free",
        "price_min": "", "price_max": "", "start_date": "", "end_date": "",
        "open_hours": "", "featured": "FALSE", "popularity_score": "",
        "status": "ongoing",
    }
    repo.append_rows(SheetName.EXHIBITIONS, [
        # general source + photo medium → kept
        {**base, "id": "e1", "source": "artmap", "source_url": "https://s/1",
         "title": "사진전", "medium": "photo", "venue_id": "v_keep",
         "artist_ids": "a_keep"},
        # general source + non-photo medium → dropped
        {**base, "id": "e2", "source": "artmap", "source_url": "https://s/2",
         "title": "회화전", "medium": "mixed", "venue_id": "v_drop",
         "artist_ids": "a_drop"},
        # photo-dedicated source keeps its row regardless of medium
        {**base, "id": "e3", "source": "gallery_lux", "source_url": "https://s/3",
         "title": "룩스전", "medium": "mixed", "venue_id": "v_keep",
         "artist_ids": ""},
    ])
    return repo


def test_general_source_rows_dropped_when_not_photo_relevant():
    catalog = build_catalog(_repo_mixed_relevance(), generated_at=GEN_AT)
    ids = {e["id"] for e in catalog["exhibitions"]}
    assert ids == {"e1", "e3"}  # artmap+mixed (e2) excluded


def test_orphan_venues_and_artists_pruned():
    catalog = build_catalog(_repo_mixed_relevance(), generated_at=GEN_AT)
    assert {v["id"] for v in catalog["venues"]} == {"v_keep"}
    assert {a["id"] for a in catalog["artists"]} == {"a_keep"}


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


def test_exhibition_json_emits_tr_and_lang_no_title_en():
    row = {
        "id": "e1", "title": "戎康友 展",
        "lang": "ja",
        "tr": json.dumps({"ko": {"title": "에비스 전", "description": "캘리포니아"}}),
        "venue_id": "", "artist_ids": "",
    }
    out = _exhibition_json(row, {}, {})
    assert out["lang"] == "ja"
    assert out["tr"]["ko"]["title"] == "에비스 전"
    assert "title_en" not in out


def test_venue_and_artist_emit_tr_no_name_en():
    v = _venue_full({"id": "v1", "name": "BOOK AND SONS",
                     "lang": "en", "tr": json.dumps({"ko": {"name": "북앤선즈"}})})
    assert v["tr"]["ko"]["name"] == "북앤선즈"
    assert "name_en" not in v
    a = _artist_full({"id": "a1", "name": "戎康友",
                      "lang": "ja", "tr": json.dumps({"ko": {"name": "에비스"}})})
    assert a["tr"]["ko"]["name"] == "에비스"
    assert "name_en" not in a


def test_tr_defaults_to_empty_dict_when_missing():
    out = _exhibition_json({"id": "e1", "title": "x", "venue_id": "", "artist_ids": ""}, {}, {})
    assert out["tr"] == {}
    assert out["lang"] is None


def test_written_file_is_strict_valid_json(tmp_path: Path):
    out = tmp_path / "exhibitions.json"
    write_catalog(_repo_with_corrupt_numerics(), str(out), generated_at=GEN_AT)
    text = out.read_text(encoding="utf-8")
    # parse_constant fires only on non-standard Infinity/NaN tokens.
    json.loads(text, parse_constant=lambda _t: (_ for _ in ()).throw(
        AssertionError("output contains a non-standard JSON constant")))
