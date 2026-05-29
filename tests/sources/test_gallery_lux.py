import json
from pathlib import Path

import httpx
import pytest
import respx

from crawler.models import SourceName
from crawler.sources.gallery_lux import (
    _BASE_URL,
    _LIST_URL,
    GalleryLuxExtractor,
    SilentlyEmptyListPage,
)

FIXTURE_DIR = Path(__file__).parent.parent / "fixtures" / "gallery_lux"

_EMPTY_HTML = "<html><body></body></html>"


def _load_fixture(name: str) -> str:
    return (FIXTURE_DIR / name).read_text(encoding="utf-8")


def _load_expected() -> list[dict]:
    return [
        json.loads(line)
        for line in (FIXTURE_DIR / "expected.jsonl").read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


@respx.mock
def test_gallery_lux_extractor_parses_cards():
    respx.get(_LIST_URL).mock(
        return_value=httpx.Response(200, text=_load_fixture("list_page_1.html"))
    )
    # Page 2 returns no cards — stops pagination
    respx.get(f"{_BASE_URL}/archive/page/2/").mock(
        return_value=httpx.Response(200, text=_EMPTY_HTML)
    )

    raws = list(GalleryLuxExtractor(delay_s=0.0).crawl())
    assert len(raws) >= 1, f"expected at least 1 exhibition, got {len(raws)}"
    assert all(r.source is SourceName.GALLERY_LUX for r in raws)

    by_url = {str(r.source_url): r for r in raws}
    for exp in _load_expected():
        actual = by_url.get(exp["source_url"])
        assert actual is not None, f"missing card for {exp['source_url']!r}"
        for k, v in exp["raw"].items():
            assert actual.raw.get(k) == v, (
                f"mismatch on {exp['source_url']} field {k!r}: "
                f"got {actual.raw.get(k)!r}, expected {v!r}"
            )


@respx.mock
def test_gallery_lux_extractor_empty_page_yields_nothing():
    respx.get(_LIST_URL).mock(
        return_value=httpx.Response(200, text="<html><body></body></html>")
    )
    raws = list(GalleryLuxExtractor(delay_s=0.0).crawl())
    assert raws == []


@respx.mock
def test_gallery_lux_extractor_raises_on_silent_zero_with_big_body():
    """A substantial HTML response with 0 parsed cards is almost always an
    anti-bot interstitial or selector drift — surface it as a real
    failure rather than silently reporting extracted=0, which is what
    the production logs were doing for months."""
    # 30 KB of meaningless markup — no <article> tags so 0 cards
    big_body = "<html><body>" + ("<div>filler</div>" * 2000) + "</body></html>"
    assert len(big_body) > 8 * 1024
    respx.get(_LIST_URL).mock(
        return_value=httpx.Response(200, text=big_body)
    )
    with pytest.raises(SilentlyEmptyListPage):
        list(GalleryLuxExtractor(delay_s=0.0).crawl())


@respx.mock
def test_gallery_lux_extractor_retries_on_403_then_succeeds(monkeypatch):
    """403 from Cloudflare-style transient block must trigger backoff
    retry, not surface as a hard failure on the first try."""
    # Speed up wait_exponential for the test
    import tenacity
    monkeypatch.setattr(tenacity.wait_exponential, "__call__", lambda *a, **kw: 0)

    fixture = _load_fixture("list_page_1.html")
    # First call → 403, second → fixture. respx side_effect order matters.
    calls = {"n": 0}

    def handler(request):
        calls["n"] += 1
        if calls["n"] == 1:
            return httpx.Response(403, text="Forbidden")
        return httpx.Response(200, text=fixture)

    respx.get(_LIST_URL).mock(side_effect=handler)
    respx.get(f"{_BASE_URL}/archive/page/2/").mock(
        return_value=httpx.Response(200, text=_EMPTY_HTML)
    )

    raws = list(GalleryLuxExtractor(delay_s=0.0).crawl())
    assert raws, "should have parsed cards on retry"
    assert calls["n"] >= 2  # at least one retry happened
