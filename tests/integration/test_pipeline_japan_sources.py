"""Smoke pipeline tests for the Japanese sources against FakeRepo."""

from __future__ import annotations

from datetime import date
from pathlib import Path

from freezegun import freeze_time

from crawler.pipeline import run_source
from crawler.sinks.base import SheetName
from crawler.sources.tokyo_photographic_art_museum import (
    TokyoPhotographicArtMuseumExtractor,
)


class _NullGeocoder:
    def geocode(
        self, query: str, country: str = "KR"
    ) -> tuple[float | None, float | None]:
        return None, None


@freeze_time("2026-05-28")
def test_tab_pipeline_smoke(header_repo, monkeypatch):
    """TAB pipeline: fixture HTML stub → extractor → upsert."""
    from pathlib import Path

    from crawler.sinks.base import SheetName
    from crawler.sources.tokyo_art_beat import TokyoArtBeatExtractor

    # Use the small html stub (1 photo event) so the test doesn't need the 2MB live page
    html = Path("tests/fixtures/tokyo_art_beat/page_with_one_event.html").read_text(
        encoding="utf-8"
    )
    monkeypatch.setattr(TokyoArtBeatExtractor, "_get", lambda self, url: html)

    report = run_source(
        extractor=TokyoArtBeatExtractor(timeout_s=5, delay_s=0),
        repo=header_repo,
        geocoder=_NullGeocoder(),
        today=date(2026, 5, 28),
    )
    assert report.failure is None
    assert report.errors == 0
    assert report.extracted == 1

    venues = header_repo.read_rows(SheetName.VENUES)
    jp_venues = [v for v in venues if v.get("country") == "JP"]
    assert jp_venues, "TAB must create at least one JP-tagged venue"
    # Test venue name from the stub
    assert any(v["name"] == "Test Venue" for v in jp_venues)


@freeze_time("2026-05-28")
def test_top_pipeline_smoke(header_repo, monkeypatch):
    """End-to-end: extractor → normalize → resolve → upsert FakeRepo.

    Uses the captured HTML fixture by monkeypatching _get.
    """
    html = Path("tests/fixtures/tokyo_photographic_art_museum/list_current.html").read_text(
        encoding="utf-8"
    )
    monkeypatch.setattr(
        TokyoPhotographicArtMuseumExtractor, "_get",
        lambda self, url: html,
    )

    report = run_source(
        extractor=TokyoPhotographicArtMuseumExtractor(delay_s=0),
        repo=header_repo,
        geocoder=_NullGeocoder(),
        today=date(2026, 5, 28),
    )
    assert report.failure is None
    assert report.errors == 0
    assert report.extracted >= 1

    venues = header_repo.read_rows(SheetName.VENUES)
    top_venues = [v for v in venues if v["name"] == "東京都写真美術館"]
    assert len(top_venues) == 1
    assert top_venues[0]["country"] == "JP"
