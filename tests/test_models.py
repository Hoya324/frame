from datetime import UTC, date, datetime

from crawler.models import (
    Artist,
    ExhibitionType,
    FeeType,
    Medium,
    NormalizedExhibition,
    Organizer,
    OrganizerType,
    RawExhibition,
    SourceName,
    Status,
    Venue,
    VenueType,
)


def _make_normalized() -> NormalizedExhibition:
    return NormalizedExhibition(
        id="abc123def456",
        source=SourceName.ARTMAP,
        source_url="https://art-map.co.kr/exhibition/view.php?idx=1",
        title="달과 도시",
        title_en=None,
        description=None,
        poster_image_url=None,
        medium=Medium.PHOTO,
        exhibition_type=ExhibitionType.SOLO,
        genre_tags=["documentary"],
        fee_type=FeeType.FREE,
        price_min=None,
        price_max=None,
        activities=[],
        start_date=date(2026, 6, 1),
        end_date=date(2026, 7, 1),
        open_hours=None,
        artist_raw_names=["김작가"],
        venue_raw_name="류가헌",
        organizer_raw_name=None,
        artist_ids=[],
        venue_id="",
        organizer_id="",
        popularity_score=None,
        featured=False,
        status=Status.UPCOMING,
        crawled_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
        warnings=[],
    )


def test_normalized_exhibition_constructs():
    exhibition = _make_normalized()
    assert exhibition.id == "abc123def456"
    assert exhibition.medium is Medium.PHOTO


def test_raw_exhibition_allows_missing_fields():
    raw = RawExhibition(
        source=SourceName.ARTMAP,
        source_url="https://art-map.co.kr/exhibition/view.php?idx=1",
        raw={"title": "untitled"},
    )
    assert raw.raw["title"] == "untitled"


def test_venue_requires_name():
    v = Venue(
        id="x",
        name="류가헌",
        venue_type=VenueType.GALLERY,
        region="서울",
        sources=["artmap"],
        first_seen_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )
    assert v.name == "류가헌"


def test_artist_organizer_construct():
    Artist(
        id="x",
        name="김작가",
        name_normalized="김작가",
        sources=["artmap"],
        first_seen_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )
    Organizer(
        id="y",
        name="한국전파진흥협회",
        name_normalized="한국전파진흥협회",
        organizer_type=OrganizerType.ASSOCIATION,
        sources=["koba"],
        first_seen_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )
