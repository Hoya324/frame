from pathlib import Path

import httpx
import respx

from crawler.models import SourceName
from crawler.sources.art_space_j import (
    ArtSpaceJExtractor,
    _clean_title,
    _parse_detail,
    _parse_list,
)

FIXTURE_DIR = Path(__file__).parent.parent / "fixtures" / "art_space_j"


def _list_html() -> str:
    return (FIXTURE_DIR / "list_current.html").read_text(encoding="utf-8")


def _detail_html() -> str:
    return (FIXTURE_DIR / "detail.html").read_text(encoding="utf-8")


def test_clean_title_strips_room_tag_and_trailing_date():
    raw = "[CUBE1]김영진 개인전_당신의 마음에도 꽃이 피기를_2026.03.06-04.30"
    assert _clean_title(raw) == "김영진 개인전_당신의 마음에도 꽃이 피기를"


def test_clean_title_handles_angle_bracket_subtitle():
    raw = "[CUBE1]손모아 개인전 <단편의 조각들 _지금 - 어디>2026.05.06-06.30"
    assert _clean_title(raw) == "손모아 개인전 <단편의 조각들 _지금 - 어디>"


def test_parse_list_extracts_title_date_url():
    items = _parse_list(_list_html())
    assert items
    first = items[0]
    assert "[CUBE" not in first["title"]
    assert first["title"] == "손모아 개인전 <단편의 조각들 _지금 - 어디>"
    assert first["source_url"].startswith("http://www.artspacej.com/")
    assert "mode=view" in first["source_url"]
    assert "idx=262" in first["source_url"]
    # Session token must not leak into the canonical URL.
    assert "PHPSESSID" not in first["source_url"]
    # The date lives in a sibling <td>, read from the whole row.
    assert first["date_range"] == "2026.05.06~2026.06.30"


def test_parse_list_dedupes():
    # Each row has an image anchor + a title anchor with the same idx; the
    # malformed ``idx=--`` upcoming teaser anchor must be dropped entirely.
    items = _parse_list(_list_html())
    urls = [it["source_url"] for it in items]
    assert len(urls) == len(set(urls))
    assert all(it["title"] for it in items)


def test_parse_detail_returns_poster_and_description():
    d = _parse_detail(_detail_html())
    assert "poster_image_url" in d and "description" in d
    assert d["poster_image_url"] == (
        "http://www.artspacej.com/uploaded/board/exhib/l__4fbb46973d9ecc90aa4dc19eb3ff293c0.jpg"
    )
    assert d["description"]
    assert "전 시 기 간" in d["description"]


@respx.mock
def test_crawl_yields_normalized_raws():
    respx.route(
        method="GET",
        url__regex=r"artspacej\.com/sub/sub03_0[13]\.php\?boardid=exhib$",
    ).mock(return_value=httpx.Response(200, text=_list_html()))
    respx.route(method="GET", url__regex=r"artspacej\.com/sub/.+mode=view.+").mock(
        return_value=httpx.Response(200, text=_detail_html())
    )
    raws = list(ArtSpaceJExtractor(delay_s=0.0).crawl())
    assert raws
    assert all(r.source is SourceName.ART_SPACE_J for r in raws)
    assert all(r.raw["category"] == "사진" for r in raws)
    assert all(r.raw["venue_region"] == "성남" for r in raws)
    # The current board feeds + the upcoming board (empty in this fixture).
    assert all("[CUBE" not in r.raw["title"] for r in raws)
