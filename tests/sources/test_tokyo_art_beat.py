"""Tokyo Art Beat (photography category) — fixture-based extractor test."""

from __future__ import annotations

import json
from pathlib import Path

from crawler.models import SourceName
from crawler.sources.tokyo_art_beat import (
    TokyoArtBeatExtractor,
    _events_to_rows,
    _extract_events_from_html,
)

_FIXTURE_DIR = Path(__file__).parent.parent / "fixtures" / "tokyo_art_beat"


def test_extractor_registered_with_jp_country():
    assert TokyoArtBeatExtractor.name == SourceName.TOKYO_ART_BEAT
    assert TokyoArtBeatExtractor.country == "JP"


def test_extract_events_from_html_unwraps_next_data():
    """The minimal HTML stub has a single photo event in __NEXT_DATA__."""
    html = (_FIXTURE_DIR / "page_with_one_event.html").read_text(encoding="utf-8")
    events = _extract_events_from_html(html)
    assert len(events) == 1
    assert events[0]["slug"] == "test-slug"
    assert events[0]["eventName"] == "Test"


def test_events_to_rows_filters_to_photography_only():
    """The 25-event subset must collapse to exactly 15 photo rows."""
    events = json.loads((_FIXTURE_DIR / "events_subset.json").read_text(encoding="utf-8"))
    rows = _events_to_rows(events)
    assert len(rows) == 15  # 15 photo + 10 non-photo in the subset
    for r in rows:
        # Every row must have JP-relevant fields
        assert r["source_url"].startswith("https://www.tokyoartbeat.com/events/")
        assert r["title"]
        assert r["venue_name"]
        assert r["date_range"]  # ISO-style "YYYY-MM-DD ~ YYYY-MM-DD"


def test_events_to_rows_drops_non_photo_categories():
    """A hand-crafted non-photo event must be dropped."""
    events = [{
        "slug": "skip-me",
        "eventName": "Painting Show",
        "scheduleStartsOn": "2026-06-01",
        "scheduleEndsOn": "2026-07-01",
        "categories": [{"fields": {"name": "絵画"}}],
        "venue": {"fields": {"fullName": "Some Gallery"}},
    }]
    assert _events_to_rows(events) == []


def test_events_to_rows_handles_missing_optional_fields():
    """Events without imageposter / localArea / venue.slug must still yield."""
    events = [{
        "slug": "minimal",
        "eventName": "Minimal Show",
        "scheduleStartsOn": "2026-06-01",
        "scheduleEndsOn": "2026-07-01",
        "categories": [{"fields": {"name": "写真"}}],
        "venue": {"fields": {"fullName": "X Gallery"}},  # no localArea, no geoInfo
        # no imageposter
    }]
    rows = _events_to_rows(events)
    assert len(rows) == 1
    r = rows[0]
    assert r["venue_name"] == "X Gallery"
    assert r["venue_region"] is None
    assert r["poster_image_url"] is None
    # No geoInfo → coords stay None so the pipeline falls back to geocoding.
    assert r["venue_lat"] is None
    assert r["venue_lng"] is None


def test_events_to_rows_extracts_venue_geoinfo():
    """When TAB ships venue.fields.geoInfo, the coords flow through so the
    pipeline can skip the unreliable name-only geocode for small galleries."""
    events = [{
        "slug": "geo",
        "eventName": "Geo Show",
        "scheduleStartsOn": "2026-06-01",
        "scheduleEndsOn": "2026-07-01",
        "categories": [{"fields": {"name": "写真"}}],
        "venue": {"fields": {
            "fullName": "PGI",
            "geoInfo": {"lat": 35.65, "lon": 139.74},
        }},
    }]
    rows = _events_to_rows(events)
    assert rows[0]["venue_lat"] == 35.65
    assert rows[0]["venue_lng"] == 139.74


def test_events_to_rows_normalizes_image_url_to_https():
    """Contentful URLs start with `//`; prepend `https:`."""
    events = [{
        "slug": "img",
        "eventName": "Img Show",
        "scheduleStartsOn": "2026-06-01",
        "scheduleEndsOn": "2026-07-01",
        "categories": [{"fields": {"name": "写真"}}],
        "venue": {"fields": {"fullName": "X"}},
        "imageposter": {"fields": {"file": {"url": "//images.ctfassets.net/foo/bar.jpg"}}},
    }]
    rows = _events_to_rows(events)
    assert rows[0]["poster_image_url"] == "https://images.ctfassets.net/foo/bar.jpg"


def test_events_to_rows_catches_english_photography_label():
    """Some TAB events may be tagged in English; whitelist must hit them too."""
    events = [{
        "slug": "en-photo",
        "eventName": "English Photo Show",
        "scheduleStartsOn": "2026-06-01",
        "scheduleEndsOn": "2026-07-01",
        "categories": [{"fields": {"name": "Photography"}}],
        "venue": {"fields": {"fullName": "X"}},
    }]
    assert len(_events_to_rows(events)) == 1
