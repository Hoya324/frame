import json
from pathlib import Path

import httpx
import respx

from crawler.sources.gmoma import GmomaExtractor, _extract_cards, _parse_detail

FIXTURE_DIR = Path(__file__).parent.parent / "fixtures" / "gmoma"

_LIST_URL = "https://gmoma.ggcf.kr/exhibitions"


def _load_fixture(name: str) -> str:
    return (FIXTURE_DIR / name).read_text(encoding="utf-8")


def _load_expected() -> list[dict]:
    return [
        json.loads(line)
        for line in (FIXTURE_DIR / "expected.jsonl").read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def _mock_site(detail_overrides: dict[int, str] | None = None) -> None:
    """Route ?progress= lists and /exhibitions/{id} details to fixtures."""
    overrides = detail_overrides or {}

    def handler(request: httpx.Request) -> httpx.Response:
        url = str(request.url)
        progress = request.url.params.get("progress")
        if progress in ("now", "yet"):
            return httpx.Response(200, text=_load_fixture(f"list_{progress}.html"))
        for i in (206, 203, 49):
            if url.endswith(f"/exhibitions/{i}"):
                if i in overrides:
                    return httpx.Response(200, text=overrides[i])
                return httpx.Response(200, text=_load_fixture(f"detail_{i}.html"))
        return httpx.Response(404)

    respx.route(url__startswith="https://gmoma.ggcf.kr/").mock(side_effect=handler)


def test_gmoma_extract_cards_parses_all_three_shows():
    """Pre-gate parse: the single li.item-list container holds 3 card anchors."""
    cards = _extract_cards(_load_fixture("list_now.html"))

    assert len(cards) == 3
    by_url = {c["source_url"]: c for c in cards}

    summer = by_url["https://gmoma.ggcf.kr/exhibitions/206"]
    assert summer["title"] == "《우리의 여름에게》"
    assert summer["date_range"] == "2026.07.16~2026.09.27"
    assert summer["venue_name"] == "경기도미술관"
    assert summer["venue_region"] == "경기"
    assert summer["poster_image_url"] == (
        "https://gmoma.ggcf.kr/storage/upload/2026/06/12/"
        "c1n5k0zdtomiBke55yLovy39QmKVE3HltHxyr8mP.jpg"
    )

    # The permanent show is open-ended ("2023. 09. 15. — ") → no date_range.
    permanent = by_url["https://gmoma.ggcf.kr/exhibitions/49"]
    assert permanent["title"] == "경기도미술관 상설전시 《멈춰서서》"
    assert permanent["date_range"] is None


def test_gmoma_extract_cards_handles_empty_upcoming_page():
    """?progress=yet renders a bare li.item-list — zero cards, no crash."""
    assert _extract_cards(_load_fixture("list_yet.html")) == []


@respx.mock
def test_gmoma_extractor_filters_out_non_media_shows():
    """All 3 live shows are painting/participatory — the media gate drops all.

    expected.jsonl is intentionally EMPTY: zero yields from the live fixture
    is the correct behavior for this general-art museum, not a parser fault.
    """
    _mock_site()

    extractor = GmomaExtractor(delay_s=0.0, with_details=True)
    raws = list(extractor.crawl())

    expected = _load_expected()
    assert expected == []  # live 2026-07-20 snapshot has no media shows
    assert raws == []

    # All three detail pages were still consulted for the strict-tier gate.
    detail_urls = {
        str(c.request.url)
        for c in respx.calls
        if "progress" not in str(c.request.url)
    }
    assert detail_urls == {
        "https://gmoma.ggcf.kr/exhibitions/206",
        "https://gmoma.ggcf.kr/exhibitions/203",
        "https://gmoma.ggcf.kr/exhibitions/49",
    }


@respx.mock
def test_gmoma_detail_description_feeds_strict_gate():
    """A show whose detail prose hits a strict compound IS emitted."""
    promoted = (
        "<html><body><div class='view-content'><p>"
        "이번 전시는 신진 작가들의 미디어 아트 신작과 대형 영상 설치를 "
        "중심으로 관람객 참여형 프로그램을 함께 선보이는 기획전이다. "
        "전시실 전관에 몰입형 상영 공간이 이어진다.</p></div></body></html>"
    )
    _mock_site(detail_overrides={206: promoted})

    extractor = GmomaExtractor(delay_s=0.0, with_details=True)
    raws = list(extractor.crawl())

    assert [str(r.source_url) for r in raws] == ["https://gmoma.ggcf.kr/exhibitions/206"]
    assert raws[0].raw["category"] == "영상"
    assert raws[0].raw["title"] == "《우리의 여름에게》"


def test_gmoma_parse_detail_extracts_description_and_artists():
    out = _parse_detail(_load_fixture("detail_203.html"))
    assert "G뮤지엄커넥트" in out["description"]
    assert out["artists"] == [
        "강익중",
        "권기수",
        "김승영",
        "박경률",
        "유현미",
        "이원석",
        "주세균",
    ]
