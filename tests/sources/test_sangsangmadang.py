"""Tests for the KT&G 상상마당 (Sangsangmadang) extractor.

The extractor targets the JSON API at /display/selectDisplayList/HD/all via POST.
Fixtures are JSON responses captured from that endpoint.
"""

import json
from pathlib import Path

import httpx
import respx

from crawler.models import SourceName
from crawler.sources.sangsangmadang import _LIST_URL, SangsangmadangExtractor

FIXTURE_DIR = Path(__file__).parent.parent / "fixtures" / "sangsangmadang"


def _load_fixture(name: str) -> str:
    return (FIXTURE_DIR / name).read_text(encoding="utf-8")


def _load_expected() -> list[dict]:
    return [
        json.loads(line)
        for line in (FIXTURE_DIR / "expected.jsonl").read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def _load_unexpected() -> list[str]:
    p = FIXTURE_DIR / "unexpected.jsonl"
    if not p.exists():
        return []
    return [line.strip() for line in p.read_text(encoding="utf-8").splitlines() if line.strip()]


@respx.mock
def test_sangsangmadang_extractor_emits_only_photo_exhibitions():
    # The extractor POSTs to the JSON API; mock page 1 and a terminating page 2
    respx.post(_LIST_URL).mock(
        side_effect=[
            httpx.Response(200, text=_load_fixture("list_all.json")),
            # page 2: empty list → extractor stops
            httpx.Response(
                200,
                text='{"paging":"","displayListInfo":{"displayList":[],"totalCount":0}}',
            ),
        ]
    )

    raws = list(SangsangmadangExtractor(delay_s=0.0).crawl())
    assert all(r.source is SourceName.SANGSANGMADANG for r in raws)

    urls = {str(r.source_url) for r in raws}

    for exp in _load_expected():
        assert exp["source_url"] in urls, (
            f"expected photo exhibition missing: {exp['source_url']!r}"
        )

    for forbidden in _load_unexpected():
        assert forbidden not in urls, f"non-photo exhibition leaked through: {forbidden!r}"

    by_url = {str(r.source_url): r for r in raws}
    for exp in _load_expected():
        for k, v in exp["raw"].items():
            assert by_url[exp["source_url"]].raw.get(k) == v, (
                f"mismatch on {exp['source_url']} field {k!r}: "
                f"got {by_url[exp['source_url']].raw.get(k)!r}, expected {v!r}"
            )


@respx.mock
def test_sangsangmadang_extractor_empty_page_yields_nothing():
    respx.post(_LIST_URL).mock(
        return_value=httpx.Response(
            200,
            text='{"paging":"","displayListInfo":{"displayList":[],"totalCount":0}}',
        )
    )
    raws = list(SangsangmadangExtractor(delay_s=0.0).crawl())
    assert raws == []
