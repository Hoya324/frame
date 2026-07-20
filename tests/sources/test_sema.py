import json
from pathlib import Path

import httpx
import respx

from crawler.models import SourceName
from crawler.sources.sema import SemaExtractor, _extract_cards, _parse_detail

FIXTURE_DIR = Path(__file__).parent.parent / "fixtures" / "sema"

_LIST_URL = "https://sema.seoul.go.kr/kr/whatson/landing?whatsonMenuDivList=EX&whenType=FROM_TODAY"

# Past the last page the server renders one EMPTY viewLink template (no
# data-idx) — pagination must stop on this, not on "no div.viewLink at all".
_EMPTY_PAGE = '<html><body><div class="pure-u-1-2 viewLink app-u-1"></div></body></html>'


def _load_fixture(name: str) -> str:
    return (FIXTURE_DIR / name).read_text(encoding="utf-8")


def _load_expected() -> list[dict]:
    return [
        json.loads(line)
        for line in (FIXTURE_DIR / "expected.jsonl").read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def _mock_list_pages(list_html: str) -> None:
    """Page 1 → fixture; any &currentPage=N page → empty template page."""

    def handler(request: httpx.Request) -> httpx.Response:
        if "currentPage" in request.url.params:
            return httpx.Response(200, text=_EMPTY_PAGE)
        return httpx.Response(200, text=list_html)

    respx.get(url__startswith="https://sema.seoul.go.kr/kr/whatson/landing").mock(
        side_effect=handler
    )


@respx.mock
def test_sema_extractor_keeps_only_media_shows():
    """12 fixture cards → only the 1 media show (서서울 미디어 소장품전).

    SeMA is a general art museum; the shared photo/film/media gate must drop
    painting/sculpture shows, and 사진미술관 cards belong to photo_sema.
    """
    _mock_list_pages(_load_fixture("list_page_1.html"))

    extractor = SemaExtractor(max_pages=1, delay_s=0.0, with_details=False)
    raws = list(extractor.crawl())

    assert all(r.source is SourceName.SEMA for r in raws)

    titles = {r.raw["title"] for r in raws}
    # 사진미술관 branch card — excluded (photo_sema covers that branch).
    assert "《마틴 파 : We Are Martin Parr》" not in titles
    # Painting show — dropped by the media gate.
    assert "2026년 한국 근대 거장전 《유영국: 산은 내 안에 있다》" not in titles

    expected = _load_expected()
    assert len(raws) == len(expected)
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


def test_sema_extract_cards_excludes_photo_sema_branch():
    """Pre-gate parse: EXM01 cards minus the 사진미술관 branch card."""
    cards = _extract_cards(_load_fixture("list_page_1.html"))

    # 12 EXM01 cards on the fixture page, 1 of them at 사진미술관.
    assert len(cards) == 11
    venues = {c["venue_name"] for c in cards}
    assert not any("사진미술관" in v for v in venues if v)
    assert all(c["venue_region"] == "서울" for c in cards)


@respx.mock
def test_sema_extractor_stops_when_page_empty():
    """The empty viewLink template page ends pagination after page 2."""
    list_html = _load_fixture("list_page_1.html")
    _mock_list_pages(list_html)

    extractor = SemaExtractor(max_pages=5, delay_s=0.0, with_details=False)
    list(extractor.crawl())

    # Page 1 (cards) + page 2 (empty template) — never pages 3-5.
    assert len(respx.calls) == 2


@respx.mock
def test_sema_detail_description_feeds_strict_gate():
    """A non-media title passes once its detail prose hits a strict compound."""
    _mock_list_pages(_load_fixture("list_page_1.html"))

    real_detail = _load_fixture("detail_1528398.html")
    # Long prose with a strict compound ("영상 설치") for the 유영국 card.
    promoted = (
        "<html><body><div class='o_body'><p>"
        "이번 전시는 대규모 영상 설치 작업을 중심으로 작가의 시대 인식을 "
        "조망하며, 아카이브와 신작을 함께 선보인다. 전시장 전관에 걸쳐 "
        "몰입형 상영 공간이 이어진다.</p></div></body></html>"
    )

    def detail_handler(request: httpx.Request) -> httpx.Response:
        ex_no = request.url.params.get("exNo")
        if ex_no == "1528398":
            return httpx.Response(200, text=real_detail)
        if ex_no == "1529410":  # 유영국 painting show, promoted via detail
            return httpx.Response(200, text=promoted)
        return httpx.Response(200, text="<html><body></body></html>")

    respx.get(url__startswith="https://sema.seoul.go.kr/kr/whatson/exhibition/detail").mock(
        side_effect=detail_handler
    )

    extractor = SemaExtractor(max_pages=1, delay_s=0.0, with_details=True)
    raws = {str(r.source_url).rsplit("=", 1)[-1]: r for r in extractor.crawl()}

    assert set(raws) == {"1528398", "1529410"}
    assert raws["1529410"].raw["category"] == "영상"
    assert "비인지적 신체성" in raws["1528398"].raw["description"]


def test_sema_parse_detail_extracts_description():
    desc = _parse_detail(_load_fixture("detail_1528398.html")).get("description", "")
    assert "비인지적 신체성" in desc
    assert len(desc) > 200
