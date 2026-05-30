import re
from pathlib import Path

import httpx
import respx

from crawler.models import SourceName
from crawler.sources.fujifilm_square import (
    FujifilmSquareExtractor,
    _extract_codes,
    _parse_detail,
)

FIXTURE_DIR = Path(__file__).parent.parent / "fixtures" / "fujifilm_square"
BASE = "https://fujifilmsquare.jp"


def _fx(name: str) -> str:
    return (FIXTURE_DIR / name).read_text(encoding="utf-8")


def test_extract_codes_finds_live_exhibitions():
    codes = _extract_codes(_fx("list.html"))
    assert "260529_01" in codes
    assert "260515_03" in codes
    # Only published anchors count; the homepage also carries commented-out
    # placeholders for not-yet-live shows, which must be ignored.
    assert "260605_03" not in codes
    assert len(codes) == 6
    assert len(set(codes)) == len(codes)  # unique


def test_parse_detail_260529_01():
    raw = _parse_detail(_fx("detail_260529_01.html"), "260529_01")
    assert raw["title"] == "東京写真月間2026 日本写真協会賞受賞作品展"
    assert raw["date_range"] == "2026年5月29日～2026年6月4日"
    assert raw["venue_name"] == "フジフイルム スクエア"
    assert raw["venue_region"] == "東京"
    assert raw["poster_image_url"] == f"{BASE}/assets/img/photo_event_260529_01_mv.jpg"
    assert raw["description"].startswith("公益社団法人日本写真協会は")
    assert raw["artists"] == []


def test_parse_detail_260515_03_solo_show():
    raw = _parse_detail(_fx("detail_260515_03.html"), "260515_03")
    assert raw["title"] == "星野 翔 写真展「律」"
    assert raw["date_range"] == "2026年5月15日～2026年6月4日"
    assert raw["poster_image_url"] == f"{BASE}/assets/img/photo_event_260515_03_mv.jpg"


@respx.mock
def test_crawl_yields_parsed_exhibitions():
    respx.get(f"{BASE}/").mock(
        return_value=httpx.Response(200, text=_fx("list.html"))
    )
    respx.get(f"{BASE}/exhibition/260529_01.html").mock(
        return_value=httpx.Response(200, text=_fx("detail_260529_01.html"))
    )
    respx.get(f"{BASE}/exhibition/260515_03.html").mock(
        return_value=httpx.Response(200, text=_fx("detail_260515_03.html"))
    )
    # Remaining detail pages aren't fixtured; treat them as unavailable so the
    # crawl skips them, mirroring a transient 404 in production.
    respx.route(
        method="GET",
        url__regex=rf"{re.escape(BASE)}/exhibition/.+\.html",
    ).mock(return_value=httpx.Response(404))

    raws = list(FujifilmSquareExtractor(delay_s=0.0).crawl())

    assert all(r.source is SourceName.FUJIFILM_SQUARE for r in raws)
    by_url = {str(r.source_url): r for r in raws}
    u1 = f"{BASE}/exhibition/260529_01.html"
    assert u1 in by_url
    assert by_url[u1].raw["title"] == "東京写真月間2026 日本写真協会賞受賞作品展"
    # Only the two fixtured detail pages resolve; the rest 404 and are skipped.
    assert len(raws) == 2


@respx.mock
def test_crawl_empty_list_yields_nothing():
    respx.get(f"{BASE}/").mock(
        return_value=httpx.Response(200, text="<html><body></body></html>")
    )
    raws = list(FujifilmSquareExtractor(delay_s=0.0).crawl())
    assert raws == []
