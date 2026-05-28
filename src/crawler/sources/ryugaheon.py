"""사진위주 류가헌 (Ryugaheon, blog.naver.com/noongamgo) — exhibition list extractor.

Strategy: Consume the Naver Blog RSS feed at
  https://rss.blog.naver.com/noongamgo.xml
which is served as static XML (no JavaScript required).  Each <item> maps to
one exhibition post.  The RSS carries up to ~50 recent items.

The gallery's official website (ryugaheon.com) is a parked domain as of 2024.
The gallery's active web presence is the Naver Blog at
  https://blog.naver.com/noongamgo
(registered under the blog ID "noongamgo"), confirmed via their Daljin gallery
directory listing (daljin.com/gallery/2372) and the RSS channel title
"사진위주 류가헌".

RSS category values (all are exhibitions — no bookstore entries appear):
  "전시1관 Gallery1"    → Gallery 1 exhibitions
  "전시2관 Gallery2"    → Gallery 2 exhibitions
  "current"            → gallery-wide announcements that are also exhibitions

There is no 책방 (bookstore) content in this RSS feed.  The gallery's
bookstore "사진책방 고래" is managed separately and does not appear in the
Naver Blog RSS.

Venue address (from daljin.com/gallery/2372, verified 2026-05-28):
  서울시 종로구 자하문로 106 아카이브빌딩 2F, B1
  (A relocation to 종로구 창성동 was announced for 2026; address will be
   updated when confirmed.)

Domain note: The plan listed www.ryugaheon.com / ryugaheon.co.kr which are
defunct or unrelated.  The live source is the Naver Blog RSS feed.
Verified 2026-05-28.
"""

from __future__ import annotations

import re
import xml.etree.ElementTree as ET
from collections.abc import Iterable

import httpx
from selectolax.parser import HTMLParser
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

from crawler.models import RawExhibition, SourceName
from crawler.sources.base import register_source

_BASE_URL = "https://blog.naver.com"
_LIST_URL = "https://rss.blog.naver.com/noongamgo.xml"
_USER_AGENT = "PhotoExhibitionCrawler/0.1 (+contact@example.com)"

_VENUE_NAME = "류가헌"
_VENUE_REGION = "서울"
_VENUE_ADDRESS = "서울시 종로구 자하문로 106 아카이브빌딩 2F, B1"

# Strip venue-hall prefix like "[전시 1관, 2관]" from post titles
_VENUE_PREFIX_RE = re.compile(r"^\[전시[^\]]*\]\s*")


class RyugaheonExtractor:
    name = SourceName.RYUGAHEON

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
                source=SourceName.RYUGAHEON,
                source_url=url,
                raw={k: v for k, v in c.items() if k != "source_url"},
            )


def _extract_cards(xml_text: str) -> list[dict]:
    """Parse a Naver Blog RSS feed into card dicts.

    Returns dicts with keys: source_url, title, venue_name, venue_region,
    venue_address, poster_image_url.

    The RSS <description> CDATA contains a snippet of the post body (HTML),
    which includes a thumbnail <img>.  The feed does not include exhibition
    date ranges — those are only available on the individual post pages.
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
        # Title — strip venue-hall prefix like "[전시 1관, 2관]"
        raw_title = (item.findtext("title") or "").strip()
        if not raw_title:
            continue
        title = _VENUE_PREFIX_RE.sub("", raw_title).strip()
        if not title:
            continue

        # Source URL — canonical form without RSS tracking params
        link = (item.findtext("link") or "").strip()
        source_url = re.sub(r"\?fromRss=true.*$", "", link).strip()
        if not source_url or not source_url.startswith("https://blog.naver.com"):
            continue

        # Poster image from HTML snippet in <description> CDATA
        desc_html = item.findtext("description") or ""
        poster: str | None = None
        if desc_html:
            desc_doc = HTMLParser(desc_html)
            img = desc_doc.css_first("img")
            if img:
                src = img.attributes.get("src", "") or ""
                poster = src if src.startswith("http") else None

        cards.append({
            "source_url": source_url,
            "title": title,
            "venue_name": _VENUE_NAME,
            "venue_region": _VENUE_REGION,
            "venue_address": _VENUE_ADDRESS,
            "poster_image_url": poster,
        })

    return cards


register_source(SourceName.RYUGAHEON, RyugaheonExtractor)
