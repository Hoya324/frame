from pathlib import Path

import httpx
import respx

from crawler.models import SourceName
from crawler.sources.place_m import PlaceMExtractor, _parse_detail, _parse_list

FIXTURE_DIR = Path(__file__).parent.parent / "fixtures" / "place_m"


def _list_html() -> str:
    return (FIXTURE_DIR / "list.html").read_text(encoding="utf-8")


def _detail_html() -> str:
    return (FIXTURE_DIR / "detail.html").read_text(encoding="utf-8")


def test_parse_list_extracts_title_artist_date_url():
    items = _parse_list(_list_html())
    assert items, "expected at least one exhibition"
    first = items[0]
    assert first["source_url"] == (
        "https://www.placem.com/schedule/2026/main/20260601/exhibition.php"
    )
    assert first["source_url"].startswith("https://www.placem.com/schedule/")
    assert first["source_url"].endswith("/exhibition.php")
    assert first["title"] == "西成"
    assert first["artists"] == ["星玄人"]
    assert "「" not in first["title"] and "」" not in first["title"]
    assert first["date_range"] == "2026.06.01~2026.06.07"


def test_parse_list_dedupes_urls():
    items = _parse_list(_list_html())
    urls = [it["source_url"] for it in items]
    assert len(urls) == len(set(urls))


def test_parse_list_skips_rows_without_links():
    # Rows like "森本眞生" are plain <td> text with no anchor and are skipped;
    # the linked mini-gallery "karuking" show is kept (once, after dedupe).
    items = _parse_list(_list_html())
    titles = [it["title"] for it in items]
    assert "西成" in titles
    assert any("伝言板" in t for t in titles)


def test_parse_detail_returns_poster_and_description():
    d = _parse_detail(_detail_html())
    assert "poster_image_url" in d and "description" in d
    # Poster is the first content image, not the site logo.
    assert d["poster_image_url"] == (
        "https://www.placem.com/schedule/2026/main/20260601/hoshi_01.jpg"
    )
    assert "placem_logo" not in d["poster_image_url"]
    assert d["description"]
    assert "西成のあいりん地区" in d["description"]


@respx.mock
def test_crawl_yields_normalized_raws():
    respx.get("https://www.placem.com/schedule/schedule.php").mock(
        return_value=httpx.Response(200, text=_list_html())
    )
    respx.route(method="GET", url__regex=r"placem\.com/schedule/\d{4}/.+").mock(
        return_value=httpx.Response(200, text=_detail_html())
    )
    raws = list(PlaceMExtractor(delay_s=0.0).crawl())
    assert raws
    assert all(r.source is SourceName.PLACE_M for r in raws)
    assert all(r.raw["category"] == "写真" for r in raws)
    assert all(r.raw["venue_region"] == "東京" for r in raws)
    first = raws[0]
    assert first.raw["title"] == "西成"
    assert first.raw["date_range"] == "2026.06.01~2026.06.07"
    assert first.raw["artists"] == ["星玄人"]
