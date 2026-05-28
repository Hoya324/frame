import json
from pathlib import Path

import httpx
import respx

from crawler.models import SourceName
from crawler.sources.gallery_lux import _BASE_URL, _LIST_URL, GalleryLuxExtractor

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
