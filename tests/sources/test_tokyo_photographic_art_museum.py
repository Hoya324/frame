"""東京都写真美術館 (Tokyo Photographic Art Museum) extractor — fixture test."""

from __future__ import annotations

import json
from pathlib import Path

from crawler.models import SourceName
from crawler.sources.tokyo_photographic_art_museum import (
    TokyoPhotographicArtMuseumExtractor,
    _extract_exhibitions,
)

_FIXTURE_DIR = Path(__file__).parent.parent / "fixtures" / "tokyo_photographic_art_museum"


def test_extractor_is_registered_with_jp_country():
    assert TokyoPhotographicArtMuseumExtractor.name == SourceName.TOKYO_PHOTOGRAPHIC_ART_MUSEUM
    assert TokyoPhotographicArtMuseumExtractor.country == "JP"


def test_extractor_yields_raw_exhibitions_matching_fixture():
    html = (_FIXTURE_DIR / "list_current.html").read_text(encoding="utf-8")
    rows = _extract_exhibitions(html)
    assert rows, "list_current.html should contain at least one exhibition card"

    expected = [
        json.loads(line)
        for line in (_FIXTURE_DIR / "expected.jsonl").read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    assert len(rows) == len(expected)
    for got, want in zip(rows, expected, strict=True):
        for k, v in want.items():
            assert got[k] == v, f"key {k!r}: got {got[k]!r}, want {v!r}"


def test_extractor_emits_jp_venue_address():
    """Every yielded row should carry the museum's address in the raw payload
    so the pipeline can geocode it via the Japanese backend."""
    html = (_FIXTURE_DIR / "list_current.html").read_text(encoding="utf-8")
    rows = _extract_exhibitions(html)
    assert rows
    for r in rows:
        assert r["venue_name"] == "東京都写真美術館"
        assert "東京都" in (r.get("venue_address") or "")


def test_extractor_dedups_by_source_url():
    """A card can appear in both video-tile (-movie) and real-card markup;
    only one row per detail URL should be yielded."""
    html = (_FIXTURE_DIR / "list_current.html").read_text(encoding="utf-8")
    rows = _extract_exhibitions(html)
    urls = [r["source_url"] for r in rows]
    assert len(urls) == len(set(urls)), "duplicate source_urls in extractor output"


def test_extractor_skips_movie_screening_urls():
    """Film screening events live under /movie/<id>/ and have one-off
    multi-date strings that can't be reduced to a normalized range —
    they're not photo exhibitions in the usual sense and must be dropped
    at the source level rather than landing as start_date=None rows."""
    html = (_FIXTURE_DIR / "list_current.html").read_text(encoding="utf-8")
    rows = _extract_exhibitions(html)
    assert rows, "fixture should have surviving exhibition cards"
    for r in rows:
        assert "/movie/" not in r["source_url"], (
            f"movie screening leaked through filter: {r['source_url']!r}"
        )
        # Every surviving row must be a real exhibition link
        assert "/exhibition/" in r["source_url"]
