from datetime import UTC, datetime

from freezegun import freeze_time

from crawler.models import (
    ExhibitionType,
    FeeType,
    Medium,
    RawExhibition,
    SourceName,
    Status,
)
from crawler.normalize import normalize_exhibition


@freeze_time("2026-05-28 12:00:00", tz_offset=0)
def test_normalize_artmap_row():
    raw = RawExhibition(
        source=SourceName.ARTMAP,
        source_url="https://art-map.co.kr/exhibition/view.php?idx=12345",
        raw={
            "title": "달과 도시 — 사진전",
            "title_en": None,
            "venue_name": "사진위주 류가헌",
            "venue_address": "서울 종로구 자하문로 106",
            "venue_region": "서울",
            "venue_district": "종로구",
            "artists": ["김작가"],
            "organizer": None,
            "date_range": "2026.06.01 ~ 2026.07.01",
            "fee_text": "무료",
            "exhibition_type_text": "개인전",
            "description": "사진작가 김작가의 첫 개인전",
            "poster_image_url": "https://art-map.co.kr/upload/p.jpg",
        },
    )
    normalized = normalize_exhibition(raw)

    assert normalized.title == "달과 도시 — 사진전"
    assert normalized.medium is Medium.PHOTO
    assert normalized.exhibition_type is ExhibitionType.SOLO
    assert normalized.fee_type is FeeType.FREE
    assert normalized.venue_raw_name == "사진위주 류가헌"
    assert normalized.venue_raw_region == "서울"
    assert normalized.artist_raw_names == ["김작가"]
    assert normalized.start_date.isoformat() == "2026-06-01"
    assert normalized.end_date.isoformat() == "2026-07-01"
    assert normalized.crawled_at == datetime(2026, 5, 28, 12, 0, tzinfo=UTC)
    assert normalized.status is Status.UNKNOWN  # status set in a later stage
    assert len(normalized.id) == 12
    assert normalized.warnings == []


@freeze_time("2026-05-28 12:00:00", tz_offset=0)
def test_normalize_records_warning_when_date_unparseable():
    raw = RawExhibition(
        source=SourceName.ARTMAP,
        source_url="https://art-map.co.kr/exhibition/view.php?idx=1",
        raw={
            "title": "X",
            "venue_name": "Y",
            "date_range": "미정",
            "fee_text": "무료",
        },
    )
    normalized = normalize_exhibition(raw)
    assert normalized.start_date is None
    assert "date_range" in normalized.warnings


def test_normalize_requires_title():
    raw = RawExhibition(
        source=SourceName.ARTMAP,
        source_url="https://art-map.co.kr/exhibition/view.php?idx=1",
        raw={"venue_name": "X"},
    )
    import pytest
    with pytest.raises(ValueError, match="title"):
        normalize_exhibition(raw)
