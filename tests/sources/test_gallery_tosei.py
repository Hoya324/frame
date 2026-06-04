from pathlib import Path

import httpx
import respx

from crawler.models import SourceName
from crawler.sources.gallery_tosei import (
    GalleryToseiExtractor,
    _extract_jp_date_range,
    _parse_list,
)

FIXTURE_DIR = Path(__file__).parent.parent / "fixtures" / "gallery_tosei"
_LIST_URL = (
    "http://www.tosei-sha.jp/TOSEI-NEW-HP/html/EXHIBITIONS/j_exhibitions.html"
)


def _list_html() -> str:
    return (FIXTURE_DIR / "list.html").read_text(encoding="utf-8")


def test_extract_jp_date_range_full():
    assert _extract_jp_date_range("2026年6月28日(日) - 7月12日(日)") == "2026.06.28~2026.07.12"


def test_extract_jp_date_range_yearless_end_backfilled():
    assert _extract_jp_date_range("2026年7月14日(火) - 8月1日(土)") == "2026.07.14~2026.08.01"


def test_extract_jp_date_range_none_when_absent():
    assert _extract_jp_date_range("作家略歴のみ") is None


def test_parse_list_extracts_current_and_next_show():
    items = _parse_list(_list_html())
    assert len(items) == 2, "expected current + next show"

    first = items[0]
    assert "河合真人写真展" in first["title"]
    assert first["date_range"] == "2026.06.28~2026.07.12"
    assert first["source_url"].startswith("http://www.tosei-sha.jp/")
    assert first["source_url"].endswith("j_Kawai.html")
    assert first["poster_image_url"] is not None
    assert first["poster_image_url"].startswith("http://www.tosei-sha.jp/")
    assert first["poster_image_url"].endswith("2606.jpg")

    second = items[1]
    assert "加納満写真展" in second["title"]
    assert second["date_range"] == "2026.07.14~2026.08.01"
    assert second["source_url"].startswith("http://www.tosei-sha.jp/")


def test_parse_list_titles_are_real_not_coming_soon():
    items = _parse_list(_list_html())
    for it in items:
        assert "Coming Soon" not in it["title"]
        assert it["title"]


@respx.mock
def test_crawl_yields_normalized_raws():
    # The live site is Shift_JIS and ``_get`` decodes ``r.content`` from it, so
    # serve the fixture as Shift_JIS bytes to exercise that decode faithfully.
    sjis = _list_html().encode("shift_jis", errors="replace")
    respx.get(_LIST_URL).mock(return_value=httpx.Response(200, content=sjis))
    respx.route(method="GET", url__regex=r"tosei-sha\.jp/.+/j_.+\.html").mock(
        return_value=httpx.Response(404)
    )
    raws = list(GalleryToseiExtractor(delay_s=0.0).crawl())
    assert raws
    assert all(r.source is SourceName.GALLERY_TOSEI for r in raws)
    assert all(r.raw["category"] == "写真" for r in raws)
    assert all(r.raw["venue_region"] == "東京" for r in raws)
