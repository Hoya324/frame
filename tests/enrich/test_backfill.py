"""Unit tests for crawler.enrich.backfill.backfill_geocodes."""

from __future__ import annotations

from datetime import UTC, datetime

from crawler.enrich.backfill import backfill_geocodes
from crawler.sinks.base import SheetName
from crawler.sinks.fake import FakeRepository

# ---------------------------------------------------------------------------
# Minimal geocoder stubs
# ---------------------------------------------------------------------------

class FixedGeocoder:
    """Always returns the same (lat, lng) pair."""

    def __init__(self, lat: float | None, lng: float | None) -> None:
        self._lat = lat
        self._lng = lng
        self.calls: list[str] = []

    def geocode(self, query: str, country: str = "KR") -> tuple[float | None, float | None]:
        self.calls.append(query)
        return self._lat, self._lng


class RaisingGeocoder:
    """Always raises RuntimeError."""

    def __init__(self) -> None:
        self.calls: list[str] = []

    def geocode(self, query: str, country: str = "KR") -> tuple[float | None, float | None]:
        self.calls.append(query)
        raise RuntimeError("geocoder exploded")


# ---------------------------------------------------------------------------
# Helper to seed venues directly into the FakeRepository
# ---------------------------------------------------------------------------

def _seed_venue(repo, *, venue_id: str, name: str = "테스트 갤러리", address: str = "서울 종로구",
                latitude: str = "", longitude: str = "") -> None:
    repo._data[SheetName.VENUES].append({
        "id": venue_id,
        "name": name,
        "address": address,
        "latitude": latitude,
        "longitude": longitude,
    })


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

def test_backfill_skips_venues_with_coords(header_repo):
    """Venues that already have both lat and lng are not geocoded."""
    _seed_venue(header_repo, venue_id="v1", latitude="37.5", longitude="127.0")
    _seed_venue(header_repo, venue_id="v2", latitude="37.6", longitude="127.1")
    _seed_venue(header_repo, venue_id="v3", latitude="", longitude="")

    geo = FixedGeocoder(lat=37.7, lng=127.2)
    report = backfill_geocodes(header_repo, geo)

    assert report.total_venues == 3
    assert report.needed_geocoding == 1
    assert report.geocoded == 1
    assert len(geo.calls) == 1  # only the incomplete venue was queried


def test_backfill_patches_coords_for_empty_venues(header_repo):
    """A venue with empty coords gets its lat/lng filled after backfill."""
    _seed_venue(header_repo, venue_id="v1", address="서울 종로구 자하문로 106",
                latitude="", longitude="")

    geo = FixedGeocoder(lat=37.5, lng=127.0)
    report = backfill_geocodes(header_repo, geo)

    assert report.geocoded == 1
    assert report.no_match == 0
    assert report.errors == 0

    # verify the row was actually patched in the store
    venues = header_repo.read_rows(SheetName.VENUES)
    assert len(venues) == 1
    assert venues[0]["latitude"] == 37.5
    assert venues[0]["longitude"] == 127.0


def test_backfill_handles_geocode_failure(header_repo):
    """When geocoder raises, errors counter increments and row stays empty."""
    _seed_venue(header_repo, venue_id="v1", latitude="", longitude="")

    geo = RaisingGeocoder()
    report = backfill_geocodes(header_repo, geo)

    assert report.errors == 1
    assert report.geocoded == 0
    assert report.no_match == 0

    # row must remain unchanged (no patch was attempted)
    venues = header_repo.read_rows(SheetName.VENUES)
    assert venues[0]["latitude"] == ""
    assert venues[0]["longitude"] == ""


def test_backfill_handles_no_match(header_repo):
    """When geocoder returns (None, None), no_match counter increments."""
    _seed_venue(header_repo, venue_id="v1", latitude="", longitude="")

    geo = FixedGeocoder(lat=None, lng=None)
    report = backfill_geocodes(header_repo, geo)

    assert report.no_match == 1
    assert report.geocoded == 0
    assert report.errors == 0

    venues = header_repo.read_rows(SheetName.VENUES)
    assert venues[0]["latitude"] == ""
    assert venues[0]["longitude"] == ""


def test_backfill_treats_partial_coords_as_missing(header_repo):
    """A venue with latitude filled but longitude empty should be re-geocoded."""
    _seed_venue(header_repo, venue_id="v1", latitude="37.5", longitude="")

    geo = FixedGeocoder(lat=37.5, lng=127.0)
    report = backfill_geocodes(header_repo, geo)

    assert report.needed_geocoding == 1
    assert report.geocoded == 1

    venues = header_repo.read_rows(SheetName.VENUES)
    assert venues[0]["longitude"] == 127.0


def test_backfill_report_is_correct_with_mixed_venues(header_repo):
    """Integration: mix of complete, partial, no-match, and error venues."""
    # v1 – already complete; should be skipped
    _seed_venue(header_repo, venue_id="v1", latitude="37.0", longitude="127.0")
    # v2 – empty coords, geocoder will succeed
    _seed_venue(header_repo, venue_id="v2", latitude="", longitude="",
                address="서울 중구 명동")
    # v3 – empty coords, no address/name — no_match
    _seed_venue(header_repo, venue_id="v3", name="", address="", latitude="", longitude="")

    class MixedGeocoder:
        def geocode(self, query: str, country: str = "KR") -> tuple[float | None, float | None]:
            if query:
                return 37.5, 127.0
            return None, None

    report = backfill_geocodes(header_repo, MixedGeocoder())

    assert report.total_venues == 3
    assert report.needed_geocoding == 2
    assert report.geocoded == 1
    assert report.no_match == 1
    assert report.errors == 0


def test_backfill_single_patch_rows_call(header_repo, monkeypatch):
    """All successful patches are sent in a single patch_rows() call."""
    _seed_venue(header_repo, venue_id="v1", latitude="", longitude="")
    _seed_venue(header_repo, venue_id="v2", latitude="", longitude="")

    patch_calls: list[list[dict]] = []
    original_patch = header_repo.patch_rows

    def counting_patch(sheet, rows):
        patch_calls.append(list(rows))
        original_patch(sheet, rows)

    monkeypatch.setattr(header_repo, "patch_rows", counting_patch)

    geo = FixedGeocoder(lat=37.5, lng=127.0)
    backfill_geocodes(header_repo, geo)

    assert len(patch_calls) == 1  # exactly one batch
    assert len(patch_calls[0]) == 2  # both venues in the same batch


# ---------------------------------------------------------------------------
# Country-aware geocoder tests (Task 8)
# ---------------------------------------------------------------------------

class _RecordingGeocoder:
    def __init__(self):
        self.calls: list[tuple[str, str]] = []

    def geocode(
        self, query: str, country: str = "KR"
    ) -> tuple[float | None, float | None]:
        self.calls.append((query, country))
        return 35.6, 139.7


def test_backfill_passes_country_to_geocoder():
    repo = FakeRepository()
    now = datetime.now(UTC).isoformat()
    # Seed a JP venue with empty coords
    repo.append_rows(SheetName.VENUES, [
        {
            "id": "v_jp_1",
            "name": "東京都写真美術館",
            "venue_type": "museum",
            "address": "東京都目黒区三田1-13-3",
            "country": "JP",
            "first_seen_at": now,
            "updated_at": now,
        },
    ])

    g = _RecordingGeocoder()
    report = backfill_geocodes(repo, g)
    assert report.geocoded == 1
    assert g.calls == [("東京都目黒区三田1-13-3", "JP")]


def test_backfill_defaults_country_to_KR_for_legacy_rows():
    """Existing KR venues with no country column still geocode via KR backend."""
    repo = FakeRepository()
    now = datetime.now(UTC).isoformat()
    repo.append_rows(SheetName.VENUES, [
        {
            "id": "v_kr_legacy",
            "name": "서울 어떤 갤러리",
            "venue_type": "gallery",
            "address": "서울특별시 종로구",
            # no "country" column
            "first_seen_at": now,
            "updated_at": now,
        },
    ])

    g = _RecordingGeocoder()
    report = backfill_geocodes(repo, g)
    assert report.geocoded == 1
    assert g.calls == [("서울특별시 종로구", "KR")]
