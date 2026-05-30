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
def test_gallery_lux_extractor_retries_interstitial_then_succeeds(monkeypatch):
    """A 200-OK response whose body lacks <article> is almost always a
    transient anti-bot interstitial served to the runner IP — exactly what
    killed the source in production (770 bytes, no cards). It must be
    retried with backoff like a 403, not surfaced as a hard failure on the
    first hit."""
    import tenacity
    monkeypatch.setattr(tenacity.wait_exponential, "__call__", lambda *a, **kw: 0)

    fixture = _load_fixture("list_page_1.html")
    calls = {"n": 0}

    def handler(request):
        calls["n"] += 1
        if calls["n"] == 1:
            # 770-byte interstitial: 200 OK, no <article>
            return httpx.Response(200, text="<html><body>blocked</body></html>")
        return httpx.Response(200, text=fixture)

    respx.get(_LIST_URL).mock(side_effect=handler)
    respx.get(f"{_BASE_URL}/archive/page/2/").mock(
        return_value=httpx.Response(200, text=_EMPTY_HTML)
    )

    raws = list(GalleryLuxExtractor(delay_s=0.0).crawl())
    assert raws, "should have parsed cards after retrying past the interstitial"
    assert calls["n"] >= 2  # at least one retry happened


@respx.mock
def test_gallery_lux_extractor_raises_when_page_one_has_no_article_tag(monkeypatch):
    """A real WordPress archive page renders many <article> elements,
    one per exhibition card. If page 1 has NONE, we got an anti-bot
    interstitial, a redirect, or markup drift — even when status is
    200. The previous version returned silently in that case, which
    is what masked the bug in production for months.

    gallery_lux's archive has years of history; it can never be
    legitimately empty. So 'no <article>' that survives every retry is
    unconditionally a failure for this source."""
    import tenacity
    monkeypatch.setattr(tenacity.wait_exponential, "__call__", lambda *a, **kw: 0)
    respx.get(_LIST_URL).mock(
        return_value=httpx.Response(200, text="<html><body></body></html>")
    )
    with pytest.raises(SilentlyEmptyListPage):
        list(GalleryLuxExtractor(delay_s=0.0).crawl())


@respx.mock
def test_gallery_lux_extractor_raises_when_big_body_has_no_article_tag(monkeypatch):
    """Belt-and-suspenders: a substantial response that lacks <article>
    tags is also a failure — covers the interstitial-with-padding case
    where an attacker hides a CF challenge inside <div> noise."""
    import tenacity
    monkeypatch.setattr(tenacity.wait_exponential, "__call__", lambda *a, **kw: 0)
    big_body = "<html><body>" + ("<div>filler</div>" * 2000) + "</body></html>"
    respx.get(_LIST_URL).mock(
        return_value=httpx.Response(200, text=big_body)
    )
    with pytest.raises(SilentlyEmptyListPage):
        list(GalleryLuxExtractor(delay_s=0.0).crawl())


@respx.mock
def test_gallery_lux_extractor_pagination_terminates_silently_when_page_2_empty():
    """When page 1 succeeds (has <article> + cards) and page 2 returns
    nothing, we should terminate pagination silently — the raise is
    only for page 1 specifically, because that's the smoking-gun
    indicator of an interstitial or drift."""
    page_1 = _load_fixture("list_page_1.html")
    respx.get(_LIST_URL).mock(return_value=httpx.Response(200, text=page_1))
    respx.get(f"{_BASE_URL}/archive/page/2/").mock(
        return_value=httpx.Response(200, text="<html><body></body></html>")
    )
    raws = list(GalleryLuxExtractor(delay_s=0.0).crawl())
    assert raws, "page 1 should have produced cards from the fixture"


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
