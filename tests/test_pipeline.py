from collections.abc import Iterable
from datetime import date

from freezegun import freeze_time

from crawler.models import (
    RawExhibition,
    SourceName,
    Status,
)
from crawler.pipeline import recompute_stale_status, run_source
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


@freeze_time("2026-05-28")
def test_run_source_persists_price_breakdown_and_venue_address(
    header_repo: FakeHeaderRepo, null_geocoder: NullGeocoder
):
    """Detail-page enrichment (price tiers / notes / venue address) must round-trip
    from the raw payload into Exhibitions + Venues rows."""
    import json

    raw = RawExhibition(
        source=SourceName.ARTMAP,
        source_url="https://art-map.co.kr/exhibition/view.php?idx=777",
        raw={
            "title": "Tier Test",
            "venue_name": "사비나미술관",
            "venue_address": "서울 은평구 진관1로 93",
            "artists": ["질라 로이테네거"],
            "date_range": "2026.06.01 ~ 2026.07.01",
            "exhibition_type_text": "개인전",
            "price_min": 0,
            "price_max": 10000,
            "price_breakdown": [
                {"label": "성인", "amount": 10000},
                {"label": "어린이 및 청소년", "amount": 8000},
                {"label": "36개월 미만 유아", "amount": 0},
            ],
            "price_notes": "장애인 50% 할인",
        },
    )
    extractor = _DummyExtractor([raw])
    report = run_source(
        extractor=extractor,
        repo=header_repo,
        geocoder=null_geocoder,
        today=date(2026, 5, 28),
    )

    assert report.failure is None
    exh_rows = header_repo.read_rows(SheetName.EXHIBITIONS)
    assert len(exh_rows) == 1
    row = exh_rows[0]

    # price_breakdown lands as JSON-encoded list
    decoded = json.loads(row["price_breakdown"])
    assert decoded == [
        {"label": "성인", "amount": 10000},
        {"label": "어린이 및 청소년", "amount": 8000},
        {"label": "36개월 미만 유아", "amount": 0},
    ]
    assert row["price_notes"] == "장애인 50% 할인"
    assert row["fee_type"] == "partial"

    # And the venue gets the street address from the detail page
    venues = header_repo.read_rows(SheetName.VENUES)
    assert len(venues) == 1
    assert venues[0]["address"] == "서울 은평구 진관1로 93"


@freeze_time("2026-05-28")
def test_run_source_skips_malformed_state_rows_instead_of_aborting(
    header_repo: FakeHeaderRepo, null_geocoder: NullGeocoder, caplog
):
    import logging
    caplog.set_level(logging.WARNING, logger="crawler.pipeline")
    """Regression: empty datetime cells in an entity sheet must not abort the crawl.

    Earlier the row hydrators called `datetime.fromisoformat(r["first_seen_at"])`
    directly, so any blank `first_seen_at` propagated as
    `ValueError: Invalid isoformat string: ''` and killed every source for the
    whole run (the failure surfaces *before* `extractor.crawl()` is even called,
    so all sources report 0/0/0/0/1 with the same message).
    """
    # Seed three broken rows that would each individually have blown up the old
    # hydrators: empty datetimes, empty id, and a stray blank row.
    header_repo.append_rows(SheetName.VENUES, [
        {
            "id": "v_broken",
            "name": "Broken Venue",
            "first_seen_at": "",  # ← the original crash trigger
            "updated_at": "",
        },
        {
            "id": "",  # blank id — also skip
            "name": "Nameless",
            "first_seen_at": "2026-05-01T00:00:00+00:00",
            "updated_at": "2026-05-01T00:00:00+00:00",
        },
        {},  # entirely blank row
    ])

    extractor = _DummyExtractor([_raw(1, "A")])
    report: SourceReport = run_source(
        extractor=extractor,
        repo=header_repo,
        geocoder=null_geocoder,
        today=date(2026, 5, 28),
    )

    assert report.failure is None
    assert report.extracted == 1
    assert report.new >= 1
    # The crawl should have logged warnings about the skipped rows
    skip_warnings = [r for r in caplog.records if "skipping malformed row" in r.getMessage()]
    assert skip_warnings, "expected at least one skip warning for the broken venue rows"


@freeze_time("2026-06-15")
def test_run_source_skips_status_recompute_when_flag_off(
    header_repo: FakeHeaderRepo,
    null_geocoder: NullGeocoder,
):
    """run-all toggles recompute_status=False to amortize the cost across all sources."""
    stale_row = {
        "id": "stale001",
        "source": "artmap",
        "status": Status.UPCOMING.value,  # WRONG – should be past
        "source_url": "https://art-map.co.kr/exhibition/view.php?idx=999",
        "title": "Stale",
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

    extractor = _DummyExtractor([_raw(1, "Brand New")])
    report = run_source(
        extractor=extractor,
        repo=header_repo,
        geocoder=null_geocoder,
        today=date(2026, 6, 15),
        recompute_status=False,
    )

    assert report.failure is None
    rows_by_id = {r["id"]: r for r in header_repo.read_rows(SheetName.EXHIBITIONS)}
    # Stale row stays stale; this batch did not recompute.
    assert rows_by_id["stale001"]["status"] == Status.UPCOMING.value

    # Now drive the global recompute (what run-all does once after all sources).
    patched = recompute_stale_status(header_repo, today=date(2026, 6, 15))
    assert patched >= 1
    rows_by_id = {r["id"]: r for r in header_repo.read_rows(SheetName.EXHIBITIONS)}
    assert rows_by_id["stale001"]["status"] == Status.PAST.value


def test_recompute_stale_status_noop_when_all_current(header_repo: FakeHeaderRepo):
    """An empty sheet (no stale rows) returns 0 without raising."""
    patched = recompute_stale_status(header_repo, today=date(2026, 5, 28))
    assert patched == 0


def test_venue_from_row_defaults_country_to_KR():
    """A legacy row without a `country` column hydrates as KR."""
    from datetime import UTC, datetime

    from crawler.pipeline import _venue_from_row

    row = {
        "id": "v_kr",
        "name": "Existing Korean Venue",
        "venue_type": "gallery",
        "first_seen_at": datetime.now(UTC).isoformat(),
        "updated_at": datetime.now(UTC).isoformat(),
        # no "country" column — legacy row from before migration
    }
    v = _venue_from_row(row)
    assert v is not None
    assert v.country == "KR"


def test_venue_from_row_reads_country_when_present():
    from datetime import UTC, datetime

    from crawler.pipeline import _venue_from_row

    row = {
        "id": "v_jp",
        "name": "東京都写真美術館",
        "venue_type": "museum",
        "country": "JP",
        "first_seen_at": datetime.now(UTC).isoformat(),
        "updated_at": datetime.now(UTC).isoformat(),
    }
    v = _venue_from_row(row)
    assert v is not None
    assert v.country == "JP"


@freeze_time("2026-05-28")
def test_run_source_stamps_country_on_new_venues(
    header_repo: FakeHeaderRepo,
    null_geocoder: NullGeocoder,
):
    """A JP extractor's new venues land in the sheet with country=JP."""

    class _JpExtractor:
        name = SourceName.ARTMAP  # any registered name works for the test
        country = "JP"

        def crawl(self):
            yield RawExhibition(
                source=SourceName.ARTMAP,
                source_url="https://example.jp/exhibition/1",
                raw={
                    "title": "Tokyo Test Show",
                    "venue_name": "Tokyo Test Museum",
                    "venue_address": "東京都目黒区三田1-13-3",
                    "artists": ["Hiroshi Sugimoto"],
                    "date_range": "2026.06.01 ~ 2026.07.01",
                    "fee_text": "무료",
                    "exhibition_type_text": "개인전",
                },
            )

    report = run_source(
        extractor=_JpExtractor(),
        repo=header_repo,
        geocoder=null_geocoder,
        today=date(2026, 5, 28),
    )
    assert report.failure is None

    venues = header_repo.read_rows(SheetName.VENUES)
    jp_venues = [v for v in venues if v["name"] == "Tokyo Test Museum"]
    assert len(jp_venues) == 1
    assert jp_venues[0]["country"] == "JP"


@freeze_time("2026-05-28")
def test_run_source_passes_country_to_geocoder(header_repo: FakeHeaderRepo):
    """Geocoder receives the extractor's country so the resolver can dispatch."""

    received: list[tuple[str, str]] = []

    class _RecordingGeocoder:
        def geocode(
            self, query: str, country: str = "KR"
        ) -> tuple[float | None, float | None]:
            received.append((query, country))
            return 35.6, 139.7

    class _JpExtractor:
        name = SourceName.ARTMAP
        country = "JP"

        def crawl(self):
            yield RawExhibition(
                source=SourceName.ARTMAP,
                source_url="https://example.jp/exhibition/2",
                raw={
                    "title": "X",
                    "venue_name": "JP Venue",
                    "venue_address": "東京都新宿区",
                    "artists": [],
                    "date_range": "2026.06.01 ~ 2026.07.01",
                },
            )

    run_source(
        extractor=_JpExtractor(),
        repo=header_repo,
        geocoder=_RecordingGeocoder(),
        today=date(2026, 5, 28),
    )
    assert len(received) == 1
    query, country = received[0]
    assert country == "JP"
    assert "東京都" in query
