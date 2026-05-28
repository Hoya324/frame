import json
from pathlib import Path

import httpx
import respx

from crawler.models import SourceName
from crawler.sources.canon_gallery import _LIST_URL, CanonGalleryExtractor

FIXTURE_DIR = Path(__file__).parent.parent / "fixtures" / "canon_gallery"

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
def test_canon_gallery_extractor_parses_cards():
    respx.post(_LIST_URL).mock(
        return_value=httpx.Response(200, text=_load_fixture("list_page_1.html"))
    )

    raws = list(CanonGalleryExtractor(max_pages=1, delay_s=0.0).crawl())
    assert len(raws) >= 1, f"expected at least 1 exhibition, got {len(raws)}"
    assert all(r.source is SourceName.CANON_GALLERY for r in raws)

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
def test_canon_gallery_extractor_empty_response_yields_nothing():
    respx.post(_LIST_URL).mock(
        return_value=httpx.Response(200, text=_EMPTY_HTML)
    )
    raws = list(CanonGalleryExtractor(max_pages=1, delay_s=0.0).crawl())
    assert raws == []
