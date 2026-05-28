from collections.abc import Iterable
from datetime import date

from freezegun import freeze_time

from crawler.models import (
    RawExhibition,
    SourceName,
    Status,
)
from crawler.pipeline import run_source
from crawler.reporter import SourceReport
from crawler.sinks.base import SheetName
from tests.conftest import FakeHeaderRepo, NullGeocoder


class _DummyExtractor:
    name = SourceName.ARTMAP

    def __init__(self, raws: list[RawExhibition]) -> None:
        self.raws = raws

    def crawl(self) -> Iterable[RawExhibition]:
        yield from self.raws


def _raw(idx: int, title: str) -> RawExhibition:
    return RawExhibition(
        source=SourceName.ARTMAP,
        source_url=f"https://art-map.co.kr/exhibition/view.php?idx={idx}",
        raw={
            "title": title,
            "venue_name": "류가헌",
            "artists": ["김작가"],
            "date_range": "2026.06.01 ~ 2026.07.01",
            "fee_text": "무료",
            "exhibition_type_text": "개인전",
        },
    )


@freeze_time("2026-05-28")
def test_run_source_end_to_end(header_repo: FakeHeaderRepo, null_geocoder: NullGeocoder):
    extractor = _DummyExtractor([_raw(1, "A"), _raw(2, "B")])

    report: SourceReport = run_source(
        extractor=extractor,
        repo=header_repo,
        geocoder=null_geocoder,
        today=date(2026, 5, 28),
    )

    assert report.name == "artmap"
    assert report.extracted == 2
    assert report.new == 2  # both new
    exh_rows = header_repo.read_rows(SheetName.EXHIBITIONS)
    assert {r["title"] for r in exh_rows} == {"A", "B"}
    # status was computed
    for r in exh_rows:
        assert r["status"] == Status.UPCOMING.value
    # one venue created and reused (artist too)
    assert len(header_repo.read_rows(SheetName.VENUES)) == 1
    assert len(header_repo.read_rows(SheetName.ARTISTS)) == 1


@freeze_time("2026-05-28")
def test_run_source_isolates_item_failure(header_repo: FakeHeaderRepo, null_geocoder: NullGeocoder):
    # second item is missing title → normalize raises → item skipped
    bad = RawExhibition(
        source=SourceName.ARTMAP,
        source_url="https://art-map.co.kr/exhibition/view.php?idx=99",
        raw={"venue_name": "류가헌"},
    )
    extractor = _DummyExtractor([_raw(1, "A"), bad, _raw(2, "B")])

    report = run_source(
        extractor=extractor,
        repo=header_repo,
        geocoder=null_geocoder,
        today=date(2026, 5, 28),
    )

    assert report.extracted == 3
    assert report.new == 2
    assert report.errors == 1
    assert report.failure is None  # not promoted to source failure


@freeze_time("2026-06-15")
def test_run_source_recomputes_status_for_stale_rows(
    header_repo: FakeHeaderRepo,
    null_geocoder: NullGeocoder,
):
    """A pre-existing exhibition still marked 'upcoming' gets recomputed to 'past'."""

    # Pre-seed EXHIBITIONS with a past exhibition still labelled upcoming.
    # Its date range was 2026-01-01 ~ 2026-01-31 (ended 4.5 months ago).
    stale_row = {
        "id": "stale001",
        "source": "artmap",
        "status": Status.UPCOMING.value,   # WRONG – should be past
        "source_url": "https://art-map.co.kr/exhibition/view.php?idx=999",
        "title": "Stale Exhibition",
        "title_en": "",
        "description": "",
        "poster_image_url": "",
        "medium": "photo",
        "exhibition_type": "solo",
        "genre_tags": "",
        "fee_type": "free",
        "price_min": "",
        "price_max": "",
        "activities": "",
        "start_date": "2026-01-01",
        "end_date": "2026-01-31",
        "open_hours": "",
        "artist_ids": "",
        "venue_id": "",
        "organizer_id": "",
        "popularity_score": "",
        "featured": "FALSE",
        "crawled_at": "2026-01-01T00:00:00+00:00",
        "updated_at": "2026-01-01T00:00:00+00:00",
        "_warnings": "",
    }
    header_repo.append_rows(SheetName.EXHIBITIONS, [stale_row])

    # Crawl a brand-new exhibition; the stale one is NOT in today's batch.
    extractor = _DummyExtractor([_raw(42, "Brand New")])

    report = run_source(
        extractor=extractor,
        repo=header_repo,
        geocoder=null_geocoder,
        today=date(2026, 6, 15),
    )

    assert report.failure is None

    rows_by_id = {r["id"]: r for r in header_repo.read_rows(SheetName.EXHIBITIONS)}
    # The stale row must now be past
    assert rows_by_id["stale001"]["status"] == Status.PAST.value
    # The new exhibition is upcoming (2026-06-01 ~ 2026-07-01, today = 2026-06-15 → ongoing)
    brand_new = [r for r in rows_by_id.values() if r["title"] == "Brand New"][0]
    assert brand_new["status"] == Status.ONGOING.value
    # The updated count must include the status-only patch for stale001
    assert report.updated >= 1


class _FlakyGeocoder:
    """Raises on every call. Simulates Kakao API outage / 403."""

    def geocode(self, query: str) -> tuple[float | None, float | None]:
        import httpx
        raise httpx.HTTPStatusError(
            "403 Forbidden",
            request=httpx.Request("GET", "https://dapi.kakao.com/x"),
            response=httpx.Response(403),
        )


@freeze_time("2026-05-28")
def test_run_source_survives_geocoder_failure(header_repo: FakeHeaderRepo):
    """Geocoder errors must not drop the venue or fail the item. Coordinates are
    just left blank; the exhibition and venue still land in the sheet."""
    extractor = _DummyExtractor([_raw(1, "X")])

    report = run_source(
        extractor=extractor,
        repo=header_repo,
        geocoder=_FlakyGeocoder(),
        today=date(2026, 5, 28),
    )

    assert report.failure is None
    assert report.errors == 0  # geocode failure is NOT an item failure
    assert report.extracted == 1
    assert report.new >= 1

    venues = header_repo.read_rows(SheetName.VENUES)
    assert len(venues) == 1
    # No coordinates, but venue exists
    assert venues[0]["latitude"] == ""
    assert venues[0]["longitude"] == ""

    exhibitions = header_repo.read_rows(SheetName.EXHIBITIONS)
    assert len(exhibitions) == 1
    assert exhibitions[0]["venue_id"] == venues[0]["id"]
