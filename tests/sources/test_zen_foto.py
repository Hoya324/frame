from pathlib import Path

import httpx
import respx

from crawler.models import SourceName
from crawler.sources.zen_foto import (
    ZenFotoExtractor,
    _extract_jp_date_range,
    _parse_detail,
    _parse_list,
)

FIXTURE_DIR = Path(__file__).parent.parent / "fixtures" / "zen_foto"
_KITAKAMI_URL = (
    "https://zen-foto.jp/jp/exhibition/"
    "shoko-hashimoto-%E2%80%9Ckitakami-river%E2%80%9D"
)


def _list_html() -> str:
    return (FIXTURE_DIR / "list.html").read_text(encoding="utf-8")


def _detail_html() -> str:
    return (FIXTURE_DIR / "detail_kitakami.html").read_text(encoding="utf-8")


def test_extract_jp_date_range_full_years():
    text = "会期：2026年1月29日（木） — 2026年3月14日（土）"
    assert _extract_jp_date_range(text) == "2026.01.29~2026.03.14"


def test_extract_jp_date_range_yearless_end_backfilled():
    text = "会期：2026年3月27日（金） — 5月30日（土） トークイベント"
    assert _extract_jp_date_range(text) == "2026.03.27~2026.05.30"


def test_extract_jp_date_range_none_when_absent():
    assert _extract_jp_date_range("作家紹介のみ、日付なし") is None


def test_parse_list_yields_six_encoded_urls():
    items = _parse_list(_list_html())
    assert len(items) == 6
    assert all(u.startswith("https://zen-foto.jp/jp/exhibition/") for u in items)
    assert all(u.isascii() for u in items)
    assert _KITAKAMI_URL in items


def test_parse_detail_pulls_title_date_poster():
    d = _parse_detail(_detail_html())
    assert d["title"] == "橋本照嵩 写真展「北上川」"
    assert d["date_range"] == "2026.03.27~2026.05.30"
    assert d["poster_image_url"].startswith("https://")
    assert d["description"].startswith("禅フォトギャラリー")


@respx.mock
def test_crawl_yields_normalized_raws():
    respx.get("https://zen-foto.jp/jp/exhibitions").mock(
        return_value=httpx.Response(200, text=_list_html())
    )
    respx.route(
        method="GET",
        url__regex=r"zen-foto\.jp/jp/exhibition/.+",
    ).mock(return_value=httpx.Response(200, text=_detail_html()))

    raws = list(ZenFotoExtractor(delay_s=0.0).crawl())

    assert len(raws) == 6
    assert all(r.source is SourceName.ZEN_FOTO for r in raws)
    by_url = {str(r.source_url): r for r in raws}
    top = by_url[_KITAKAMI_URL]
    assert top.raw["title"] == "橋本照嵩 写真展「北上川」"
    assert top.raw["date_range"] == "2026.03.27~2026.05.30"
    assert top.raw["category"] == "写真"
    assert top.raw["venue_region"] == "東京"
