import json
from pathlib import Path

import httpx
import respx

from crawler.models import SourceName
from crawler.sources.acc import AccExtractor, _extract_cards, _parse_detail

FIXTURE_DIR = Path(__file__).parent.parent / "fixtures" / "acc"

_LIST_URL = "https://www.acc.go.kr/main/exhibition.do?PID=0202"


def _load_fixture(name: str) -> str:
    return (FIXTURE_DIR / name).read_text(encoding="utf-8")


def _load_expected() -> list[dict]:
    return [
        json.loads(line)
        for line in (FIXTURE_DIR / "expected.jsonl").read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def _mock_site() -> None:
    """Route list pages 1-2 (page 3+ re-serves page 1) and the two captured
    detail fixtures; every other detail 404s (detail failures are tolerated)."""
    page_1 = _load_fixture("list_page_1.html")
    page_2 = _load_fixture("list_page_2.html")

    def handler(request: httpx.Request) -> httpx.Response:
        url = str(request.url)
        if "action=Read" in url:
            for bnkey in ("EM_0000009294", "EM_0000009471"):
                if bnkey in url:
                    return httpx.Response(200, text=_load_fixture(f"detail_{bnkey}.html"))
            return httpx.Response(404)
        if "pageIndex=2" in url:
            return httpx.Response(200, text=page_2)
        return httpx.Response(200, text=page_1)  # page 1 and out-of-range re-serves

    respx.route(url__startswith="https://www.acc.go.kr/main/exhibition.do").mock(
        side_effect=handler
    )


def test_extract_cards_parses_list_fields():
    cards = _extract_cards(_load_fixture("list_page_1.html"))

    assert len(cards) == 8
    by_title = {c["title"]: c for c in cards}
    film = by_title["ACC 필름앤비디오 《아시아의 장치들》"]
    assert film["date_range"] == "2026-03-19 ~ 2026-09-27"
    assert film["fee_text"] == "무료"
    assert film["source_url"].endswith("bnkey=EM_0000009294")
    assert film["poster_image_url"].startswith("https://www.acc.go.kr/")
    # The curated one-liner is captured for the media gate's short text.
    assert film["summary"]


@respx.mock
def test_crawl_matches_expected():
    _mock_site()

    raws = list(AccExtractor(delay_s=0.0).crawl())

    assert all(r.source is SourceName.ACC for r in raws)
    expected = _load_expected()
    assert len(raws) == len(expected) == 3
    by_url = {str(r.source_url): r for r in raws}
    for exp in expected:
        assert exp["source_url"] in by_url, (
            f"Expected URL not found: {exp['source_url']}\n"
            f"Available URLs: {list(by_url.keys())}"
        )
        actual = by_url[exp["source_url"]]
        for k, v in exp["raw"].items():
            assert actual.raw.get(k) == v, (
                f"mismatch on {exp['source_url']} field {k!r}: "
                f"got {actual.raw.get(k)!r}, expected {v!r}"
            )


@respx.mock
def test_crawl_gates_out_non_media_shows():
    _mock_site()

    titles = {r.raw["title"] for r in AccExtractor(delay_s=0.0).crawl()}

    # Craft/history/children shows on the fixture pages must be dropped.
    all_titles = {
        c["title"]
        for page in ("list_page_1.html", "list_page_2.html")
        for c in _extract_cards(_load_fixture(page))
    }
    dropped = all_titles - titles
    assert len(dropped) == len(all_titles) - 3
    assert "ACC 필름앤비디오 《아시아의 장치들》" in titles
    assert "ACC 국제교류특별전 〈자밀 프라이즈: 무빙 이미지〉" in titles


@respx.mock
def test_crawl_stops_when_pages_repeat():
    _mock_site()

    extractor = AccExtractor(delay_s=0.0, max_pages=5)
    list(extractor.crawl())

    # Pages 1, 2, then one repeat (page 3 re-serves page 1 → no new cards).
    list_calls = [
        c for c in respx.calls if "action=Read" not in str(c.request.url)
    ]
    assert len(list_calls) == 3


def test_parse_detail_canonicalizes_labeled_date():
    detail = _parse_detail(_load_fixture("detail_EM_0000009294.html"))
    assert detail.get("description")
    # The labeled 기간 value "2026.3.19.(목) - 9.27.(일)" canonicalizes.
    assert detail.get("date_range") == "2026.03.19~2026.09.27"
