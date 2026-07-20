import json
import re
from pathlib import Path

import httpx
import respx

from crawler.models import SourceName
from crawler.sources.moca_busan import MocaBusanExtractor, _extract_cards, _parse_detail

FIXTURE_DIR = Path(__file__).parent.parent / "fixtures" / "moca_busan"

_DETAIL_ID_RE = re.compile(r"/moca/exhibition0\d/(\d+)$")


def _load_fixture(name: str) -> str:
    return (FIXTURE_DIR / name).read_text(encoding="utf-8")


def _load_expected() -> list[dict]:
    return [
        json.loads(line)
        for line in (FIXTURE_DIR / "expected.jsonl").read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def _mock_site() -> None:
    current = _load_fixture("list_page_1.html")
    upcoming = _load_fixture("list_upcoming_page_1.html")

    def handler(request: httpx.Request) -> httpx.Response:
        url = str(request.url)
        m = _DETAIL_ID_RE.search(url.split("?")[0])
        if m:
            fixture = FIXTURE_DIR / f"detail_{m.group(1)}.html"
            if fixture.exists():
                return httpx.Response(200, text=fixture.read_text(encoding="utf-8"))
            return httpx.Response(404)
        if "exhibition02" in url:
            return httpx.Response(200, text=upcoming)
        return httpx.Response(200, text=current)  # exhibition01 + repeats

    respx.route(url__startswith="https://www.busan.go.kr/moca/").mock(side_effect=handler)


def test_extract_cards_permanent_range_is_none():
    cards = _extract_cards(_load_fixture("list_page_1.html"))

    assert [c["title"] for c in cards] == ["Re: 새-새-의자", "패트릭 블랑: 수직정원"]
    # "2018. 6. 16.(토) ~ 상설" has no parseable end → date_range None.
    assert all(c["date_range"] is None for c in cards)
    assert all(c["venue_name"] == "부산현대미술관" for c in cards)


def test_extract_cards_upcoming_parses_full_ranges():
    cards = _extract_cards(_load_fixture("list_upcoming_page_1.html"))

    by_title = {c["title"]: c for c in cards}
    assert by_title["소장품섬_뉴미디어와 미디어"]["date_range"] == "2026.12.11~2027.03.07"
    # Year-only teaser ranges ("2026. ~ 2027.") stay None but the card is kept.
    assert by_title["커미션 프로젝트 Ⅰ_마르코 바로티"]["date_range"] is None


@respx.mock
def test_crawl_matches_expected():
    _mock_site()

    raws = list(MocaBusanExtractor(delay_s=0.0).crawl())

    assert all(r.source is SourceName.MOCA_BUSAN for r in raws)
    expected = _load_expected()
    assert len(raws) == len(expected) == 1
    by_url = {str(r.source_url): r for r in raws}
    for exp in expected:
        assert exp["source_url"] in by_url
        actual = by_url[exp["source_url"]]
        for k, v in exp["raw"].items():
            assert actual.raw.get(k) == v, (
                f"mismatch on field {k!r}: got {actual.raw.get(k)!r}, expected {v!r}"
            )


@respx.mock
def test_crawl_gates_out_permanent_installations():
    # The two current shows are non-media permanent installations; only the
    # upcoming 뉴미디어 collection show passes the gate.
    _mock_site()

    titles = {r.raw["title"] for r in MocaBusanExtractor(delay_s=0.0).crawl()}

    assert titles == {"소장품섬_뉴미디어와 미디어"}
    assert "Re: 새-새-의자" not in titles
    assert "패트릭 블랑: 수직정원" not in titles


@respx.mock
def test_crawl_stops_on_repeating_pages():
    _mock_site()

    extractor = MocaBusanExtractor(delay_s=0.0, max_pages=5)
    list(extractor.crawl())

    list_calls = [
        c
        for c in respx.calls
        if not _DETAIL_ID_RE.search(str(c.request.url).split("?")[0])
    ]
    # Each board: page 1 + one repeat that adds nothing new → 2 calls × 2 boards.
    assert len(list_calls) == 4


def test_parse_detail_extracts_description():
    detail = _parse_detail(_load_fixture("detail_1714078.html"))
    assert "뉴미디어" in detail.get("description", "")
    assert len(detail["description"]) >= 60
