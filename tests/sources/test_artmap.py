import json
from pathlib import Path

import httpx
import respx

from crawler.models import SourceName
from crawler.sources.artmap import ArtmapExtractor


FIXTURE_DIR = Path(__file__).parent.parent / "fixtures" / "artmap"


def _load_fixture(name: str) -> str:
    return (FIXTURE_DIR / name).read_text(encoding="utf-8")


def _load_expected() -> list[dict]:
    return [
        json.loads(line)
        for line in (FIXTURE_DIR / "expected.jsonl").read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


@respx.mock
def test_artmap_extractor_parses_first_three_cards():
    list_html = _load_fixture("list_page_1.html")
    # The extractor POSTs to /data/new_exhibition.php
    respx.post("https://art-map.co.kr/data/new_exhibition.php").mock(
        return_value=httpx.Response(200, text=list_html)
    )

    extractor = ArtmapExtractor(max_batches=1, delay_s=0.0)
    raws = list(extractor.crawl())
    assert len(raws) >= 3, f"expected at least 3 cards, got {len(raws)}"
    assert all(r.source is SourceName.ARTMAP for r in raws)

    expected = _load_expected()
    by_url = {str(r.source_url): r for r in raws}
    for exp in expected:
        actual = by_url[exp["source_url"]]
        for k, v in exp["raw"].items():
            assert actual.raw.get(k) == v, (
                f"mismatch on {exp['source_url']} field {k!r}: "
                f"got {actual.raw.get(k)!r}, expected {v!r}"
            )


@respx.mock
def test_artmap_extractor_stops_when_page_empty():
    list_html = _load_fixture("list_page_1.html")
    call_count = 0

    def side_effect(request: httpx.Request) -> httpx.Response:
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            return httpx.Response(200, text=list_html)
        # Subsequent batches return empty (no cards)
        return httpx.Response(200, text="<html><body></body></html>")

    respx.post("https://art-map.co.kr/data/new_exhibition.php").mock(side_effect=side_effect)

    extractor = ArtmapExtractor(max_batches=5, delay_s=0.0)
    raws = list(extractor.crawl())
    # Should stop after batch 2 (empty) rather than continuing to batch 5
    assert len(raws) >= 3
    assert call_count == 2, f"expected 2 POST calls, got {call_count}"
