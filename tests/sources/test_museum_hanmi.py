import json
from pathlib import Path

import httpx
import respx

from crawler.models import SourceName
from crawler.sources.museum_hanmi import MuseumHanmiExtractor, _parse_detail

FIXTURE_DIR = Path(__file__).parent.parent / "fixtures" / "museum_hanmi"

_LIST_URL = "https://museumhanmi.or.kr/exhibition/"


def _load_fixture(name: str) -> str:
    return (FIXTURE_DIR / name).read_text(encoding="utf-8")


def _load_expected() -> list[dict]:
    return [
        json.loads(line)
        for line in (FIXTURE_DIR / "expected.jsonl").read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


@respx.mock
def test_museum_hanmi_extractor_parses_cards():
    list_html = _load_fixture("list_page_1.html")
    # Page 1 returns real cards; subsequent pages return empty
    call_count = 0

    def side_effect(request: httpx.Request) -> httpx.Response:
        nonlocal call_count
        call_count += 1
        return httpx.Response(200, text=list_html)

    respx.get(_LIST_URL, params={"pgs": "1"}).mock(side_effect=side_effect)

    extractor = MuseumHanmiExtractor(max_pages=1, delay_s=0.0, with_details=False)
    raws = list(extractor.crawl())
    assert len(raws) >= 1, f"expected at least 1 card, got {len(raws)}"
    assert all(r.source is SourceName.MUSEUM_HANMI for r in raws)

    expected = _load_expected()
    by_url = {str(r.source_url): r for r in raws}
    for exp in expected:
        actual = by_url.get(exp["source_url"])
        assert actual is not None, f"missing card for url {exp['source_url']!r}"
        for k, v in exp["raw"].items():
            assert actual.raw.get(k) == v, (
                f"mismatch on {exp['source_url']} field {k!r}: "
                f"got {actual.raw.get(k)!r}, expected {v!r}"
            )


@respx.mock
def test_museum_hanmi_extractor_stops_when_page_empty():
    list_html = _load_fixture("list_page_1.html")
    call_count = 0

    def side_effect(request: httpx.Request) -> httpx.Response:
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            return httpx.Response(200, text=list_html)
        return httpx.Response(200, text="<html><body></body></html>")

    respx.get(_LIST_URL, params={"pgs": "1"}).mock(side_effect=side_effect)
    respx.get(_LIST_URL, params={"pgs": "2"}).mock(side_effect=side_effect)

    extractor = MuseumHanmiExtractor(max_pages=5, delay_s=0.0, with_details=False)
    raws = list(extractor.crawl())
    assert len(raws) >= 1
    assert call_count == 2, f"expected 2 GET calls, got {call_count}"


def test_museum_hanmi_parse_detail_extracts_description():
    html = _load_fixture("detail_uelsmann.html")
    out = _parse_detail(html)
    desc = out.get("description", "")
    assert desc.startswith("뮤지엄한미는 2026년 하반기 개관 예정인")
    assert "조합인화 기법" in desc
    assert len(desc) > 200
