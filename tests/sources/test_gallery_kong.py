import json
from pathlib import Path

import httpx
import respx

from crawler.models import SourceName
from crawler.sources.gallery_kong import _BASE_URL, _LIST_URL, GalleryKongExtractor

FIXTURE_DIR = Path(__file__).parent.parent / "fixtures" / "gallery_kong"

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
def test_gallery_kong_extractor_parses_cards():
    respx.get(_LIST_URL).mock(
        return_value=httpx.Response(200, text=_load_fixture("list_page_1.html"))
    )
    # Mock detail pages
    respx.get(f"{_BASE_URL}/2022_KwakIntan_palette").mock(
        return_value=httpx.Response(200, text=_load_fixture("detail_2022_KwakIntan.html"))
    )
    respx.get(f"{_BASE_URL}/2022__MichaelKenna").mock(
        return_value=httpx.Response(200, text=_load_fixture("detail_2022_MichaelKenna.html"))
    )
    respx.get(f"{_BASE_URL}/2022_jenpak_IntotheVoid").mock(
        return_value=httpx.Response(200, text=_load_fixture("detail_2022_jenpak.html"))
    )

    raws = list(GalleryKongExtractor(delay_s=0.0).crawl())
    assert len(raws) >= 1, f"expected at least 1 exhibition, got {len(raws)}"
    assert all(r.source is SourceName.GALLERY_KONG for r in raws)

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
def test_gallery_kong_extractor_empty_page_yields_nothing():
    respx.get(_LIST_URL).mock(
        return_value=httpx.Response(200, text=_EMPTY_HTML)
    )
    raws = list(GalleryKongExtractor(delay_s=0.0).crawl())
    assert raws == []


@respx.mock
def test_gallery_kong_extractor_retries_on_403_then_succeeds(monkeypatch):
    """Wix-hosted konggallery.com intermittently 403s data-center IPs;
    retry-with-backoff usually clears it within a few seconds. Verify
    the source recovers instead of bubbling the first 403 up as a hard
    failure."""
    import tenacity
    monkeypatch.setattr(tenacity.wait_exponential, "__call__", lambda *a, **kw: 0)

    fixture = _load_fixture("list_page_1.html")
    calls = {"n": 0}

    def handler(request):
        calls["n"] += 1
        if calls["n"] == 1:
            return httpx.Response(403, text="Forbidden")
        return httpx.Response(200, text=fixture)

    respx.get(_LIST_URL).mock(side_effect=handler)
    # Detail pages still need to be mocked for the full pipeline to run.
    respx.get(f"{_BASE_URL}/2022_KwakIntan_palette").mock(
        return_value=httpx.Response(200, text=_load_fixture("detail_2022_KwakIntan.html"))
    )
    respx.get(f"{_BASE_URL}/2022__MichaelKenna").mock(
        return_value=httpx.Response(200, text=_load_fixture("detail_2022_MichaelKenna.html"))
    )
    respx.get(f"{_BASE_URL}/2022_jenpak_IntotheVoid").mock(
        return_value=httpx.Response(200, text=_load_fixture("detail_2022_jenpak.html"))
    )

    raws = list(GalleryKongExtractor(delay_s=0.0).crawl())
    assert raws, "should have parsed cards after retry"
    assert calls["n"] >= 2  # at least one 403 → retry → success
