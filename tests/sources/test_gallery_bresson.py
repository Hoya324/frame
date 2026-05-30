import json
from pathlib import Path

import httpx
import respx

from crawler.models import SourceName
from crawler.sources.gallery_bresson import (
    GalleryBressonExtractor,
    _extract_date_range,
    _parse_post,
)

FIXTURE_DIR = Path(__file__).parent.parent / "fixtures" / "gallery_bresson"


def _posts() -> list[dict]:
    return json.loads((FIXTURE_DIR / "posts_current.json").read_text(encoding="utf-8"))


def _by_id(pid: int) -> dict:
    return next(p for p in _posts() if p["id"] == pid)


def test_extract_date_range_dotted_tilde():
    assert _extract_date_range("전시 2025.8.1~8.30 입니다") == "2025.08.01~2025.08.30"


def test_extract_date_range_padded_with_trailing_dot():
    assert _extract_date_range("기간 2025.04.21.~05.06") == "2025.04.21~2025.05.06"


def test_extract_date_range_end_is_day_only():
    assert _extract_date_range("2024.11.20~29") == "2024.11.20~2024.11.29"


def test_extract_date_range_spaces_weekday_parens_endash():
    # The richest in-the-wild form: spaces around dots, weekday parens, en-dash.
    text = "전시 일정 : 2025. 1. 16 (목) – 1. 25 (토) 전시 장소"
    assert _extract_date_range(text) == "2025.01.16~2025.01.25"


def test_extract_date_range_picks_first_when_multiple():
    # The body repeats sub-period rows after the overall span; take the span.
    text = "2025.8.1~8.30 1부 2025.8.1~8.10 2부 2025.8.11~8.20"
    assert _extract_date_range(text) == "2025.08.01~2025.08.30"


def test_extract_date_range_none_when_absent():
    assert _extract_date_range("작가 소개만 있고 날짜는 없음") is None


def test_parse_post_full():
    raw = _parse_post(_by_id(22089))
    assert raw is not None
    assert raw["title"] == "사진 정신(Foto Geist) 정기전_Memory"
    assert raw["date_range"] == "2025.08.01~2025.08.30"
    assert (
        raw["poster_image_url"]
        == "http://gallerybresson.com/wp-content/uploads/2025/07/홈.jpg"
    )
    assert raw["venue_name"] == "갤러리 브레송"
    assert raw["venue_region"] == "서울"
    assert raw["category"] == "사진"
    assert raw["artists"] == []
    assert raw["description"].startswith("Memory")


def test_parse_post_without_body_date_yields_no_range():
    # 大甲媽租_장재웅 carries its dates only on the poster image, not in the body.
    raw = _parse_post(_by_id(21981))
    assert raw is not None
    assert raw["title"] == "大甲媽租_장재웅"
    assert raw["date_range"] is None
    assert raw["poster_image_url"].endswith(".jpg")


@respx.mock
def test_crawl_yields_all_posts():
    respx.route(
        method="GET",
        url__regex=r"gallerybresson\.com/index\.php",
    ).mock(
        return_value=httpx.Response(
            200, text=(FIXTURE_DIR / "posts_current.json").read_text(encoding="utf-8")
        )
    )

    raws = list(GalleryBressonExtractor(delay_s=0.0).crawl())

    assert len(raws) == 8
    assert all(r.source is SourceName.GALLERY_BRESSON for r in raws)
    by_url = {str(r.source_url): r for r in raws}
    assert "http://gallerybresson.com/?p=22089" in by_url
    assert by_url["http://gallerybresson.com/?p=22089"].raw["title"] == (
        "사진 정신(Foto Geist) 정기전_Memory"
    )


@respx.mock
def test_crawl_empty_list_yields_nothing():
    respx.route(
        method="GET",
        url__regex=r"gallerybresson\.com/index\.php",
    ).mock(return_value=httpx.Response(200, text="[]"))

    raws = list(GalleryBressonExtractor(delay_s=0.0).crawl())
    assert raws == []
