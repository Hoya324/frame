"""gallery NoW / 갤러리 나우 (blog.naver.com/gallerynow) — exhibition list extractor.

Strategy: Consume the Naver Blog RSS feed at
  https://rss.blog.naver.com/gallerynow.xml
served as static XML (no JavaScript required). Each <item> maps to one post.
The feed carries up to ~50 recent items.

gallery NoW is a Seoul photography-rooted gallery that now also shows
painting and sculpture. Its active web presence is the Naver Blog at
  https://blog.naver.com/gallerynow
(blogId "gallerynow"), confirmed via the RSS channel title "gallery NoW".

RSS <category> values observed (2026-06-05 fixture, 50 items):
  "전시소식"   (39) → exhibition announcements
  "기타전시"   ( 1) → other exhibitions
  "아트페어"   ( 9) → art fairs (EXCLUDED — not a venue exhibition)
  "gallery NoW"( 1) → gallery notice (EXCLUDED — not in allow-set)
We keep only items carrying an allowed exhibition category.

Date range: unlike the ryugaheon feed, gallery NoW's <description> CDATA body
snippet contains the exhibition period as text, e.g.
  "전시 기간 : 2026.05.06(수)-05.30(토)"
We strip the HTML to text and run the shared extract_date_range() to
canonicalize it to "YYYY.MM.DD~YYYY.MM.DD".

Medium: gallery NoW is a photo-rooted gallery and our goal is surfacing photo
solo shows, so we seed raw["category"] = "사진" → map_medium classifies these
as PHOTO. The RSS snippets lack the "사진" keyword, so without seeding every
item defaults to MIXED. Tradeoff (accepted): the gallery's occasional
painting/sculpture shows get over-tagged as photo.

Venue address (from the gallery's own post bodies, verified 2026-06-05):
  서울시 강남구 언주로 152길 16
"""

from __future__ import annotations

import re
import xml.etree.ElementTree as ET
from collections.abc import Iterable
from urllib.parse import urljoin

import httpx
from selectolax.parser import HTMLParser
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

from crawler.models import RawExhibition, SourceName
from crawler.sources._detail import extract_date_range
from crawler.sources.base import register_source

_BASE_URL = "https://blog.naver.com"
_LIST_URL = "https://rss.blog.naver.com/gallerynow.xml"
_USER_AGENT = "PhotoExhibitionCrawler/0.1 (+contact@example.com)"

_VENUE_NAME = "gallery NoW"
_VENUE_REGION = "서울"
_VENUE_ADDRESS = "서울시 강남구 언주로 152길 16"

# Keep only exhibition categories; skip art fairs (아트페어) and gallery notices.
_ALLOWED_CATEGORIES = {"전시소식", "기타전시"}


class GalleryNowExtractor:
    name = SourceName.GALLERY_NOW

    def __init__(
        self,
        delay_s: float = 1.0,
        timeout_s: float = 20.0,
    ) -> None:
        self.delay_s = delay_s
        self._client = httpx.Client(
            timeout=timeout_s,
            headers={"User-Agent": _USER_AGENT},
            follow_redirects=True,
        )

    @retry(
        retry=retry_if_exception_type(httpx.TransportError),
        wait=wait_exponential(multiplier=1, min=1, max=16),
        stop=stop_after_attempt(3),
        reraise=True,
    )
    def _get(self, url: str) -> str:
        r = self._client.get(url)
        r.raise_for_status()
        return r.text

    def crawl(self) -> Iterable[RawExhibition]:
        xml_text = self._get(_LIST_URL)
        cards = _extract_cards(xml_text)

        seen: set[str] = set()
        for c in cards:
            url = c["source_url"]
            if url in seen:
                continue
            seen.add(url)
            yield RawExhibition(
                source=SourceName.GALLERY_NOW,
                source_url=url,
                raw={k: v for k, v in c.items() if k != "source_url"},
            )


def _extract_cards(xml_text: str) -> list[dict]:
    """Parse the gallery NoW Naver Blog RSS feed into card dicts.

    Returns dicts with keys: source_url, title, venue_name, venue_region,
    venue_address, poster_image_url, date_range, category.

    Items whose <category> elements don't include an allowed exhibition
    category are skipped (e.g. 아트페어 art fairs). The exhibition period is
    pulled from the <description> CDATA body snippet via extract_date_range().
    """
    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError:
        return []

    channel = root.find("channel")
    if channel is None:
        return []

    cards: list[dict] = []

    for item in channel.findall("item"):
        # Category filter — keep if ANY category is in the allow-set.
        categories = {(c.text or "").strip() for c in item.findall("category")}
        if not (categories & _ALLOWED_CATEGORIES):
            continue

        title = (item.findtext("title") or "").strip()
        if not title:
            continue

        # Source URL — canonical form without RSS tracking params.
        link = (item.findtext("link") or "").strip()
        source_url = re.sub(r"\?fromRss=true.*$", "", link).strip()
        if not source_url or not source_url.startswith("https://blog.naver.com"):
            continue

        # Description CDATA carries both the thumbnail <img> and the period text.
        desc_html = item.findtext("description") or ""
        poster: str | None = None
        date_range: str | None = None
        if desc_html:
            desc_doc = HTMLParser(desc_html)
            img = desc_doc.css_first("img")
            if img:
                src = (img.attributes.get("src", "") or "").strip()
                # Naver's RSS snippets often use protocol-relative (`//host/…`)
                # or site-relative paths; promote both to absolute https URLs
                # instead of dropping them.
                if src.startswith("//"):
                    poster = f"https:{src}"
                elif src.startswith("http"):
                    poster = src
                elif src.startswith("/"):
                    poster = urljoin(_BASE_URL, src)
                else:
                    poster = None
            date_range = extract_date_range(desc_doc.text())

        cards.append({
            "source_url": source_url,
            "title": title,
            "venue_name": _VENUE_NAME,
            "venue_region": _VENUE_REGION,
            "venue_address": _VENUE_ADDRESS,
            "poster_image_url": poster,
            "date_range": date_range,
            # Photo-rooted venue: seed 사진 so map_medium → PHOTO.
            "category": "사진",
        })

    return cards


register_source(SourceName.GALLERY_NOW, GalleryNowExtractor)
