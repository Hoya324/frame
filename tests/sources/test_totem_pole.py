from pathlib import Path

import httpx
import respx

from crawler.models import SourceName
from crawler.sources.totem_pole import (
    TotemPoleExtractor,
    _parse_detail,
    _parse_list,
)

FIXTURE_DIR = Path(__file__).parent.parent / "fixtures" / "totem_pole"


def _list_html() -> str:
    return (FIXTURE_DIR / "list.html").read_text(encoding="utf-8")


def _detail_html() -> str:
    return (FIXTURE_DIR / "detail.html").read_text(encoding="utf-8")


def test_parse_list_finds_dated_exhibitions():
    items = _parse_list(_list_html())
    assert items, "expected at least one current/upcoming exhibition"
    for it in items:
        assert it["source_url"].startswith("https://tppg.jp/")
        assert it["title"]
    assert any(it["date_range"] and "~" in it["date_range"] for it in items)


def test_parse_list_extracts_real_current_show():
    items = _parse_list(_list_html())
    by_url = {it["source_url"]: it for it in items}
    sunburn = by_url["https://tppg.jp/sunburn/"]
    assert sunburn["title"] == "Sunburn"
    assert sunburn["artists"] == ["蔡嘉辰 / Jiachen Cai"]
    assert sunburn["date_range"] == "2026.05.26~2026.06.07"


def test_parse_list_extracts_upcoming_show_without_medium_label():
    items = _parse_list(_list_html())
    by_url = {it["source_url"]: it for it in items}
    # "新井 悠史 / Yushi Arai 写真展「OVERALIVE 1」..." — the 写真展 label must be
    # stripped from the artist and the quoted title kept clean.
    overalive = by_url["https://tppg.jp/overalive-1/"]
    assert overalive["title"] == "OVERALIVE 1"
    assert overalive["artists"] == ["新井 悠史 / Yushi Arai"]
    assert overalive["date_range"] == "2026.06.09~2026.06.14"


def test_parse_list_dedupes_and_excludes_nav():
    items = _parse_list(_list_html())
    urls = [it["source_url"] for it in items]
    assert len(urls) == len(set(urls))
    for bad in ("/about/", "/access/", "/contact/", "/exhibitions/"):
        assert all(not u.endswith(bad) for u in urls)


def test_parse_detail_returns_poster_and_description():
    d = _parse_detail(_detail_html())
    assert "poster_image_url" in d and "description" in d
    assert d["poster_image_url"] == "https://tppg.jp/wp/wp-content/uploads/2026/03/1.jpg"
    assert d["description"] and "日焼け" in d["description"]


@respx.mock
def test_crawl_yields_normalized_raws():
    respx.get("https://tppg.jp/").mock(
        return_value=httpx.Response(200, text=_list_html())
    )
    respx.route(method="GET", url__regex=r"tppg\.jp/[^/]+/$").mock(
        return_value=httpx.Response(200, text=_detail_html())
    )
    raws = list(TotemPoleExtractor(delay_s=0.0).crawl())
    assert raws
    assert all(r.source is SourceName.TOTEM_POLE for r in raws)
    assert all(r.raw["category"] == "写真" for r in raws)
    assert all(r.raw["venue_name"] == "Totem Pole Photo Gallery" for r in raws)
