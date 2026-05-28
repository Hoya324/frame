from datetime import UTC, datetime

from freezegun import freeze_time

from crawler.models import (
    ExhibitionType,
    Medium,
    NormalizedExhibition,
    SourceName,
    Status,
)
from crawler.resolver.entities import EntityState, resolve_entities


def _exh(**over) -> NormalizedExhibition:
    base = dict(
        id="x",
        source=SourceName.ARTMAP,
        source_url="https://art-map.co.kr/exhibition/view.php?idx=1",
        title="달과 도시",
        medium=Medium.PHOTO,
        exhibition_type=ExhibitionType.SOLO,
        artist_raw_names=["김작가"],
        venue_raw_name="류가헌",
        organizer_raw_name=None,
        status=Status.UNKNOWN,
        crawled_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )
    base.update(over)
    return NormalizedExhibition.model_validate(base)


@freeze_time("2026-05-28")
def test_resolver_creates_new_entities_when_state_empty():
    state = EntityState(artists=[], venues=[], organizers=[], overrides=[])
    out = resolve_entities(_exh(), state)
    assert len(out.new_artists) == 1
    assert len(out.new_venues) == 1
    assert len(out.new_organizers) == 0
    assert out.exhibition.artist_ids == [out.new_artists[0].id]
    assert out.exhibition.venue_id == out.new_venues[0].id
    assert out.exhibition.organizer_id == out.new_venues[0].id  # fallback


@freeze_time("2026-05-28")
def test_resolver_reuses_existing_artist_by_normalized_name():
    from crawler.models import Artist
    from crawler.normalize.dedup import artist_id
    from crawler.normalize.text import normalize_name

    existing = Artist(
        id=artist_id(normalize_name("김작가")),
        name="김작가",
        name_normalized=normalize_name("김작가"),
        sources=["naver"],
        first_seen_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )
    state = EntityState(artists=[existing], venues=[], organizers=[], overrides=[])
    out = resolve_entities(_exh(), state)
    assert out.new_artists == []
    assert out.exhibition.artist_ids == [existing.id]


@freeze_time("2026-05-28")
def test_resolver_applies_override_for_artist_alias():
    from crawler.models import Artist
    from crawler.normalize.dedup import artist_id
    from crawler.normalize.text import normalize_name

    canonical = Artist(
        id=artist_id(normalize_name("김주현")),
        name="김주현",
        name_normalized=normalize_name("김주현"),
        sources=["naver"],
        first_seen_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )
    override = {
        "entity_type": "artist",
        "match_pattern": "김작가",
        "canonical_id": canonical.id,
        "note": "stage name",
    }
    state = EntityState(artists=[canonical], venues=[], organizers=[], overrides=[override])
    out = resolve_entities(_exh(), state)
    assert out.exhibition.artist_ids == [canonical.id]
    assert out.new_artists == []


@freeze_time("2026-05-28")
def test_resolver_propagates_venue_raw_region_to_new_venue():
    """venue_raw_region from NormalizedExhibition is passed to a newly created Venue."""
    state = EntityState(artists=[], venues=[], organizers=[], overrides=[])
    out = resolve_entities(_exh(venue_raw_region="서울"), state)
    assert len(out.new_venues) == 1
    assert out.new_venues[0].region == "서울"


@freeze_time("2026-05-28")
def test_resolver_does_not_overwrite_existing_venue_region():
    """venue_raw_region is NOT applied when the venue already exists with a non-null region."""
    from crawler.models import Venue, VenueType
    from crawler.normalize.dedup import venue_id

    existing = Venue(
        id=venue_id("류가헌", None),
        name="류가헌",
        venue_type=VenueType.OTHER,
        region="부산",          # existing non-null region
        sources=["naver"],
        first_seen_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )
    state = EntityState(artists=[], venues=[existing], organizers=[], overrides=[])
    out = resolve_entities(_exh(venue_raw_region="서울"), state)
    # No new venue; the existing one is reused
    assert out.new_venues == []
    # Existing venue object is not mutated
    assert existing.region == "부산"
