import json
from pathlib import Path

import httpx
import respx

from crawler.models import SourceName
from crawler.sources._media import media_category
from crawler.sources.ilmin import (
    IlminExtractor,
    _extract_date,
    _extract_links,
    _parse_detail,
)

FIXTURE_DIR = Path(__file__).parent.parent / "fixtures" / "ilmin"

_LIST_URL = "https://ilmin.org/exhibitions/current/"
_DETAIL_URL = "https://ilmin.org/exhibition/2026_korean-traditional-painting-uk/"


def _load_fixture(name: str) -> str:
    return (FIXTURE_DIR / name).read_text(encoding="utf-8")


def _load_expected() -> list[dict]:
    return [
        json.loads(line)
        for line in (FIXTURE_DIR / "expected.jsonl").read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


# A minimal Divi-shaped detail page for an in-scope (photo) show, used to
# prove the crawl yields when the media gate passes. The live 2026-07-20
# fixture is a Korean-painting show that the gate correctly drops.
_PHOTO_DETAIL_HTML = """
<html><head>
<meta property="og:title" content="《서울 사진전: 도시의 기록》 - 일민미술관" />
<meta property="og:image" content="https://ilmin.org/wp-content/uploads/2026/09/poster.jpg" />
</head><body>
<div id="main-content">
  <div class="et_pb_code_inner">2026.9.4.(Fri) ― 2026.11.1.(Sun)</div>
  <div class="et_pb_text_inner">
    <p>일민미술관은 동시대 사진작가들의 작업을 조망하는 기획전을 개최한다.
    도시의 일상을 기록해 온 참여 작가들의 사진 연작을 한자리에 모은다.</p>
  </div>
</div>
</body></html>
"""


def test_extract_date_horizontal_bar_and_english_weekday():
    # The in-the-wild form: English weekday parens + U+2015 horizontal bar,
    # neither of which the shared extract_date_range handles on its own.
    assert _extract_date("2026.6.26.(Fri) ― 2026.8.21.(Fri)") == "2026.06.26~2026.08.21"


def test_extract_date_full_weekday_names():
    assert _extract_date("2026.9.4.(Friday) ― 2026.11.1.(Sunday)") == "2026.09.04~2026.11.01"


def test_extract_date_none_when_absent():
    assert _extract_date("일민미술관 전시 안내") is None


def test_extract_links_dedupes_card_anchors():
    # Each Divi card links to the detail page twice (poster + title anchor).
    links = _extract_links(_load_fixture("current.html"))
    assert links == [_DETAIL_URL]


def test_parse_detail_fields():
    raw = _parse_detail(_load_fixture("detail_2026_korean-traditional-painting-uk.html"))
    assert raw["title"] == "《다시 그린 세계 2026: 순수와 혼종》"
    assert raw["date_range"] == "2026.06.26~2026.08.21"
    assert raw["poster_image_url"] == (
        "https://ilmin.org/wp-content/uploads/2026/06/20260619_031537.jpg"
    )
    assert raw["venue_name"] == "일민미술관"
    assert raw["venue_region"] == "서울"
    assert raw["artists"] == []
    assert raw["description"].startswith("일민미술관은 주영한국문화원")
    assert len(raw["description"]) > 200


@respx.mock
def test_crawl_drops_non_media_show_after_parsing():
    """2026-07-20 snapshot: the sole current show is Korean painting.

    The crawl must parse it (pre-filter count 1) and then drop it at the
    media gate — 0 yields matches the empty expected.jsonl.
    """
    respx.get(_LIST_URL).mock(
        return_value=httpx.Response(200, text=_load_fixture("current.html"))
    )
    respx.get(_DETAIL_URL).mock(
        return_value=httpx.Response(
            200, text=_load_fixture("detail_2026_korean-traditional-painting-uk.html")
        )
    )

    # Pre-filter: the list parse does find the show...
    assert _extract_links(_load_fixture("current.html")) == [_DETAIL_URL]
    raw = _parse_detail(_load_fixture("detail_2026_korean-traditional-painting-uk.html"))
    # ...and it is the media gate (not a parse failure) that excludes it.
    assert media_category(raw["title"], raw["description"]) is None

    raws = list(IlminExtractor(delay_s=0.0).crawl())
    assert raws == []
    assert _load_expected() == []  # fixture snapshot agrees: 0 rows


@respx.mock
def test_crawl_yields_photo_show():
    respx.get(_LIST_URL).mock(
        return_value=httpx.Response(
            200,
            text='<a href="https://ilmin.org/exhibition/2026_photo-show/">《서울 사진전》</a>',
        )
    )
    respx.get("https://ilmin.org/exhibition/2026_photo-show/").mock(
        return_value=httpx.Response(200, text=_PHOTO_DETAIL_HTML)
    )

    raws = list(IlminExtractor(delay_s=0.0).crawl())

    assert len(raws) == 1
    (item,) = raws
    assert item.source is SourceName.ILMIN
    assert item.raw["title"] == "《서울 사진전: 도시의 기록》"
    assert item.raw["category"] == "사진"
    assert item.raw["date_range"] == "2026.09.04~2026.11.01"
    assert item.raw["poster_image_url"] == (
        "https://ilmin.org/wp-content/uploads/2026/09/poster.jpg"
    )
    assert item.raw["venue_name"] == "일민미술관"


@respx.mock
def test_crawl_survives_detail_failure():
    # A broken detail page must skip that card, not abort the crawl.
    respx.get(_LIST_URL).mock(
        return_value=httpx.Response(200, text=_load_fixture("current.html"))
    )
    respx.get(_DETAIL_URL).mock(return_value=httpx.Response(500))

    raws = list(IlminExtractor(delay_s=0.0).crawl())
    assert raws == []
