from pathlib import Path

import httpx
import respx

from crawler.models import Medium, SourceName
from crawler.normalize.categories import map_medium
from crawler.sources.gallery_now import _LIST_URL, GalleryNowExtractor, _extract_cards

FIXTURE_DIR = Path(__file__).parent.parent / "fixtures" / "gallery_now"

_EMPTY_RSS = '<?xml version="1.0" encoding="UTF-8"?><rss version="2.0"><channel></channel></rss>'

# A known 아트페어 post that MUST be excluded (category == 아트페어 only).
_ART_FAIR_URL = "https://blog.naver.com/gallerynow/224299177311"
# A known exhibition post that MUST be kept, with its canonical date range.
_EXHIBITION_URL = "https://blog.naver.com/gallerynow/224263445337"


def _load_fixture(name: str) -> str:
    return (FIXTURE_DIR / name).read_text(encoding="utf-8")


@respx.mock
def test_gallery_now_extractor_parses_cards():
    respx.get(_LIST_URL).mock(return_value=httpx.Response(200, text=_load_fixture("feed.xml")))

    raws = list(GalleryNowExtractor(delay_s=0.0).crawl())
    assert len(raws) >= 1, f"expected at least 1 exhibition, got {len(raws)}"
    assert all(r.source is SourceName.GALLERY_NOW for r in raws)
    assert all(r.raw["venue_region"] == "서울" for r in raws)
    assert all(r.raw["venue_name"] == "gallery NoW" for r in raws)
    # Photo-rooted venue seeds 사진 → every item classifies as PHOTO.
    assert all(map_medium(r.raw["category"]) is Medium.PHOTO for r in raws)


@respx.mock
def test_gallery_now_excludes_art_fair_items():
    respx.get(_LIST_URL).mock(return_value=httpx.Response(200, text=_load_fixture("feed.xml")))

    urls = {str(r.source_url) for r in GalleryNowExtractor(delay_s=0.0).crawl()}
    assert _ART_FAIR_URL not in urls
    assert _EXHIBITION_URL in urls


@respx.mock
def test_gallery_now_extracts_date_range():
    respx.get(_LIST_URL).mock(return_value=httpx.Response(200, text=_load_fixture("feed.xml")))

    by_url = {str(r.source_url): r for r in GalleryNowExtractor(delay_s=0.0).crawl()}
    card = by_url[_EXHIBITION_URL]
    assert card.raw["date_range"] == "2026.05.06~2026.05.30"
    # Photo-rooted venue: seed 사진 so map_medium classifies as PHOTO.
    assert card.raw["category"] == "사진"


@respx.mock
def test_gallery_now_strips_rss_tracking_params():
    respx.get(_LIST_URL).mock(return_value=httpx.Response(200, text=_load_fixture("feed.xml")))

    urls = [str(r.source_url) for r in GalleryNowExtractor(delay_s=0.0).crawl()]
    assert all("fromRss" not in u for u in urls)


def _rss_with_img(img_src: str, category: str = "전시소식") -> str:
    desc = f'<![CDATA[<img src="{img_src}" /> 전시 기간 : 2026.05.06(수)-05.30(토)]]>'
    return (
        '<?xml version="1.0" encoding="UTF-8"?><rss version="2.0"><channel>'
        "<item><title>테스트 전시</title>"
        f"<category>{category}</category>"
        "<link>https://blog.naver.com/gallerynow/123?fromRss=true</link>"
        f"<description>{desc}</description></item>"
        "</channel></rss>"
    )


def test_gallery_now_promotes_protocol_relative_poster():
    cards = _extract_cards(_rss_with_img("//blogthumb.pstatic.net/x.jpg?type=s3"))
    assert cards[0]["poster_image_url"] == "https://blogthumb.pstatic.net/x.jpg?type=s3"


def test_gallery_now_promotes_site_relative_poster():
    cards = _extract_cards(_rss_with_img("/img/x.jpg"))
    assert cards[0]["poster_image_url"] == "https://blog.naver.com/img/x.jpg"


def test_gallery_now_keeps_absolute_poster():
    cards = _extract_cards(_rss_with_img("https://blogthumb.pstatic.net/x.jpg"))
    assert cards[0]["poster_image_url"] == "https://blogthumb.pstatic.net/x.jpg"


def test_gallery_now_synthetic_card_extracts_date_and_skips_art_fair():
    kept = _extract_cards(_rss_with_img("https://x/x.jpg", category="전시소식"))
    assert kept[0]["date_range"] == "2026.05.06~2026.05.30"

    skipped = _extract_cards(_rss_with_img("https://x/x.jpg", category="아트페어"))
    assert skipped == []


@respx.mock
def test_gallery_now_extractor_empty_feed_yields_nothing():
    respx.get(_LIST_URL).mock(return_value=httpx.Response(200, text=_EMPTY_RSS))
    raws = list(GalleryNowExtractor(delay_s=0.0).crawl())
    assert raws == []
