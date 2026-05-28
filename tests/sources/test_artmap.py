import json
import re
from pathlib import Path

import httpx
import respx

from crawler.models import SourceName
from crawler.sources.artmap import (
    ArtmapExtractor,
    _parse_detail,
    _parse_price,
)

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
def test_artmap_extractor_parses_list_only_without_detail_fetch():
    list_html = _load_fixture("list_page_1.html")
    respx.post("https://art-map.co.kr/data/new_exhibition.php").mock(
        return_value=httpx.Response(200, text=list_html)
    )

    extractor = ArtmapExtractor(max_batches=1, delay_s=0.0, with_details=False)
    raws = list(extractor.crawl())
    assert len(raws) >= 3
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
        return httpx.Response(200, text="<html><body></body></html>")

    respx.post("https://art-map.co.kr/data/new_exhibition.php").mock(side_effect=side_effect)

    extractor = ArtmapExtractor(max_batches=5, delay_s=0.0, with_details=False)
    raws = list(extractor.crawl())
    assert len(raws) >= 3
    assert call_count == 2, f"expected 2 POST calls, got {call_count}"


@respx.mock
def test_artmap_extractor_enriches_with_detail_pages():
    """When with_details=True, each card gets fields parsed from its detail GET."""
    list_html = _load_fixture("list_page_1.html")
    free_detail = _load_fixture("detail_32332_free.html")
    paid_detail = _load_fixture("detail_32327_paid.html")

    respx.post("https://art-map.co.kr/data/new_exhibition.php").mock(
        return_value=httpx.Response(200, text=list_html)
    )
    # Route detail GETs by idx: 32332 → free fixture, everything else → paid
    # (the only idx that *needs* the free response is 32332 since the rest
    # don't appear in our assertions; reusing the paid fixture keeps respx
    # happy without forcing us to capture three more pages).
    detail_re = re.compile(r"https://art-map\.co\.kr/exhibition/view\.php\?idx=(\d+)")

    def detail_side_effect(request: httpx.Request) -> httpx.Response:
        m = detail_re.match(str(request.url))
        assert m, f"unexpected GET: {request.url}"
        idx = m.group(1)
        body = free_detail if idx == "32332" else paid_detail
        return httpx.Response(200, text=body)

    respx.get(detail_re).mock(side_effect=detail_side_effect)

    extractor = ArtmapExtractor(max_batches=1, delay_s=0.0, with_details=True)
    raws = list(extractor.crawl())
    by_url = {str(r.source_url): r for r in raws}

    free = by_url["https://art-map.co.kr/exhibition/view.php?idx=32332"]
    assert free.raw["price_min"] == 0
    assert free.raw["price_max"] == 0
    assert free.raw["artists"] == ["유영국"]
    assert free.raw["venue_address"] == "서울 중구 덕수궁길 61"
    assert "10:00" in free.raw["open_hours"]


@respx.mock
def test_artmap_extractor_keeps_list_data_when_detail_fetch_fails():
    list_html = _load_fixture("list_page_1.html")
    respx.post("https://art-map.co.kr/data/new_exhibition.php").mock(
        return_value=httpx.Response(200, text=list_html)
    )
    respx.get(re.compile(r"https://art-map\.co\.kr/exhibition/view\.php.*")).mock(
        return_value=httpx.Response(500)
    )

    extractor = ArtmapExtractor(max_batches=1, delay_s=0.0, with_details=True)
    raws = list(extractor.crawl())
    # Every list-page card still yields, just without detail enrichment
    assert len(raws) >= 3
    for r in raws:
        assert r.raw.get("title")
        assert "price_min" not in r.raw
        assert "artists" not in r.raw


# --- Parser unit tests ---


def test_parse_price_free_only():
    assert _parse_price("무료") == (0, 0)


def test_parse_price_single_amount():
    assert _parse_price("성인 10,000원") == (10000, 10000)


def test_parse_price_partial_mix_treats_free_as_floor():
    text = (
        "· 성인: 10,000원\n"
        "· 어린이 및 청소년: 8,000원\n"
        "· 36개월 미만 유아: 무료\n"
        "· 사비나미술관 멤버십 회원(가입일 기준 1년): 무료"
    )
    assert _parse_price(text) == (0, 10000)


def test_parse_price_discount_lines_excluded():
    text = (
        "· 성인: 10,000원\n"
        "· 장애인 및 동행자 1인: 50% 할인\n"
        "· 단체: 1,000원 할인"
    )
    assert _parse_price(text) == (10000, 10000)


def test_parse_price_empty():
    assert _parse_price("") == (None, None)
    assert _parse_price("   ") == (None, None)


def test_parse_detail_free_fixture():
    html = _load_fixture("detail_32332_free.html")
    out = _parse_detail(html)
    assert out["price_min"] == 0
    assert out["price_max"] == 0
    assert out["venue_address"] == "서울 중구 덕수궁길 61"
    assert out["artists"] == ["유영국"]
    assert "10:00" in out["open_hours"]
    # Numeric parse succeeded, so fee_text shortcut is suppressed
    assert "fee_text" not in out


def test_parse_detail_paid_fixture():
    html = _load_fixture("detail_32327_paid.html")
    out = _parse_detail(html)
    assert out["price_min"] == 0
    assert out["price_max"] == 10000
    assert out["venue_address"] == "서울 은평구 진관1로 93"
    assert out["artists"] == ["질라 로이테네거"]
    assert "10:00" in out["open_hours"]
    assert "fee_text" not in out


def test_parse_detail_returns_empty_when_table_missing():
    assert _parse_detail("<html><body><p>no table here</p></body></html>") == {}
