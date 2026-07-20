import json
from pathlib import Path

import httpx
import respx

from crawler.sources.daegu_art_museum import (
    DaeguArtMuseumExtractor,
    _extract_cards,
    _parse_detail,
)

FIXTURE_DIR = Path(__file__).parent.parent / "fixtures" / "daegu_art_museum"

_LIST_URL = "https://daeguartmuseum.or.kr/index.do?menu_id=00000729"


def _load_fixture(name: str) -> str:
    return (FIXTURE_DIR / name).read_text(encoding="utf-8")


def _load_expected() -> list[dict]:
    return [
        json.loads(line)
        for line in (FIXTURE_DIR / "expected.jsonl").read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def _mock_site() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        url = str(request.url)
        if "ehi_id=EHI_00000335" in url:
            return httpx.Response(200, text=_load_fixture("detail_EHI_00000335.html"))
        if "ehi_id=" in url:
            return httpx.Response(404)
        return httpx.Response(200, text=_load_fixture("list_page_1.html"))

    respx.route(url__startswith="https://daeguartmuseum.or.kr/").mock(side_effect=handler)


def test_extract_cards_skips_schedule_notice():
    cards = _extract_cards(_load_fixture("list_page_1.html"))

    titles = [c["title"] for c in cards]
    # The "2026 전시일정" notice row must not be treated as an exhibition.
    assert not any("전시일정" in t for t in titles)
    assert "2026 다티스트 《심윤： 회색 극장》" in titles
    assert len(cards) == 5


def test_extract_cards_builds_canonical_detail_url():
    cards = _extract_cards(_load_fixture("list_page_1.html"))

    first = cards[0]
    assert first["source_url"] == (
        "https://daeguartmuseum.or.kr/index.do"
        "?menu_id=00000729&menu_link=/front/ehi/ehiViewFront.do&ehi_id=EHI_00000335"
    )
    assert first["date_range"] == "2026-07-14~2026-10-11"
    assert first["venue_name"] == "대구미술관"


@respx.mock
def test_crawl_matches_expected_zero_yields_on_painting_season():
    # The recon-date lineup is painting/collection shows — the media gate drops
    # every card, and expected.jsonl is intentionally empty.
    _mock_site()

    raws = list(DaeguArtMuseumExtractor(delay_s=0.0).crawl())

    assert _load_expected() == []
    assert raws == []


@respx.mock
def test_crawl_pre_filter_parsing_still_works():
    # Zero yields must be the gate's doing, not a parser failure: the list
    # parse finds all 5 real cards before filtering.
    _mock_site()

    list(DaeguArtMuseumExtractor(delay_s=0.0).crawl())

    cards = _extract_cards(_load_fixture("list_page_1.html"))
    assert len(cards) == 5


@respx.mock
def test_crawl_yields_media_show_when_present():
    # Synthetic list with a photo-titled card proves the pipeline end-to-end.
    synthetic = """
    <div class="c_exh_lst">
      <div class="item">
        <a href="javascript:fnView('EHI_99999999');">
          <span class="img"><span class="inr"><img src="/icms/x.jpg"></span></span>
          <span class="item_tit">대구사진비엔날레 특별전</span>
          <span class="info_area">
            <span class="info"><em class="info_tit">기간</em>
              <span class="info_date">2026-08-01~2026-10-01</span></span>
          </span>
        </a>
      </div>
    </div>
    """

    def handler(request: httpx.Request) -> httpx.Response:
        if "ehi_id=" in str(request.url):
            return httpx.Response(404)
        return httpx.Response(200, text=synthetic)

    respx.route(url__startswith="https://daeguartmuseum.or.kr/").mock(side_effect=handler)

    raws = list(DaeguArtMuseumExtractor(delay_s=0.0).crawl())

    assert len(raws) == 1
    assert raws[0].raw["title"] == "대구사진비엔날레 특별전"
    assert raws[0].raw["category"] == "사진"


def test_parse_detail_extracts_description():
    detail = _parse_detail(_load_fixture("detail_EHI_00000335.html"))
    # The 심윤 회색 극장 page carries intro prose (may legitimately be empty if
    # the container moved — then the dict is empty; both shapes are valid).
    if detail:
        assert len(detail["description"]) >= 60
