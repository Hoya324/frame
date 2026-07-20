import json
from pathlib import Path

import httpx
import respx

from crawler.models import SourceName
from crawler.sources.njp_art_center import (
    NjpArtCenterExtractor,
    _parse_detail,
    _split_artists,
)

FIXTURE_DIR = Path(__file__).parent.parent / "fixtures" / "njp_art_center"

_LIST_URL = "https://njp.ggcf.kr/exhibitions"


def _load_fixture(name: str) -> str:
    return (FIXTURE_DIR / name).read_text(encoding="utf-8")


def _load_expected() -> list[dict]:
    return [
        json.loads(line)
        for line in (FIXTURE_DIR / "expected.jsonl").read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


@respx.mock
def test_njp_extractor_parses_cards():
    """Extractor parses the current-show cards from the /exhibitions page."""
    respx.get(_LIST_URL).mock(
        return_value=httpx.Response(200, text=_load_fixture("list_page_1.html"))
    )

    extractor = NjpArtCenterExtractor(delay_s=0.0, with_details=False)
    raws = list(extractor.crawl())

    assert len(raws) >= 2, f"expected at least 2 NJP cards, got {len(raws)}"
    assert all(r.source is SourceName.NJP_ART_CENTER for r in raws)
    # Single-purpose venue — every card is seeded 영상, no media gate.
    assert all(r.raw["category"] == "영상" for r in raws)

    expected = _load_expected()
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
def test_njp_extractor_merges_detail_fields():
    """Detail description + 참여작가 roster land in the raw payload."""
    respx.get(_LIST_URL).mock(
        return_value=httpx.Response(200, text=_load_fixture("list_page_1.html"))
    )
    detail_244 = _load_fixture("detail_244.html")

    def detail_handler(request: httpx.Request) -> httpx.Response:
        if str(request.url).endswith("/exhibitions/244"):
            return httpx.Response(200, text=detail_244)
        # Other detail pages: empty — the crawl must not abort on them.
        return httpx.Response(200, text="<html><body></body></html>")

    respx.get(url__regex=r"https://njp\.ggcf\.kr/exhibitions/\d+$").mock(
        side_effect=detail_handler
    )

    extractor = NjpArtCenterExtractor(delay_s=0.0, with_details=True)
    raws = {str(r.source_url): r for r in extractor.crawl()}

    star = raws["https://njp.ggcf.kr/exhibitions/244"]
    assert star.raw["artists"] == ["백남준"]
    assert "백남준미디어아트페스티벌" in star.raw["description"]
    # Cards whose detail had no prose keep their list-level fields.
    assert raws["https://njp.ggcf.kr/exhibitions/243"].raw["title"] == "달들"


@respx.mock
def test_njp_extractor_survives_detail_failure():
    """A 500 on every detail page must not abort the crawl."""
    respx.get(_LIST_URL).mock(
        return_value=httpx.Response(200, text=_load_fixture("list_page_1.html"))
    )
    respx.get(url__regex=r"https://njp\.ggcf\.kr/exhibitions/\d+$").mock(
        return_value=httpx.Response(500)
    )

    extractor = NjpArtCenterExtractor(delay_s=0.0, with_details=True)
    raws = list(extractor.crawl())

    assert len(raws) >= 2
    assert all("description" not in r.raw for r in raws)


def test_njp_parse_detail_extracts_description_and_artists():
    out = _parse_detail(_load_fixture("detail_244.html"))
    assert "백남준의 작품에 등장하는 별과 행성" in out["description"]
    assert out["artists"] == ["백남준"]
    # og:image is empty on the live CMS today — no poster override.
    assert "poster_image_url" not in out


def test_njp_split_artists_is_paren_aware():
    assert _split_artists("백남준") == ["백남준"]
    assert _split_artists("얄루, 알오에스(강류, 김시월), 레이첼 윤") == [
        "얄루",
        "알오에스(강류, 김시월)",
        "레이첼 윤",
    ]
