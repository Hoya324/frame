"""캐논 갤러리 (Canon Gallery Korea, kr.canon/canongallery) — exhibition list extractor.

Strategy: POST to the AJAX endpoint /canongallery/list/ajax with pagination params.
The canonical list page at /canongallery renders an empty ``<div class="masonry-list-row">``
and populates it client-side via jQuery AJAX.  The endpoint returns HTML ``<a>`` fragments
(not JSON) that are appended into the masonry grid.

Each page loads 20 items.  Pagination uses ``pageIndex`` (1-based) and ``pageUnit`` (20).
The response includes a JS snippet ``totalPageCount = N`` which we parse to know when
to stop.  We also stop when a page returns no items.

AJAX endpoint (verified 2026-05-28):
  POST https://kr.canon/canongallery/list/ajax
  Body: pageUnit=20&pageIndex=1

Response fragment structure:
  <a href="/canongallery/detail?gllyDispSeq=<seq>" class="masonry-item" ...>
    <div class="img"><img src="//image.kr.canon/..." alt="전시작품" ...></div>
    <div class="desc">
      <div class="txt"><p>전시 제목</p></div>
      <div class="info-list"><p>YYYY.MM.DD ~ YYYY.MM.DD</p></div>
    </div>
  </a>

Domain note: The original site canon-ci.co.kr ceased operation around mid-2022.
The operator migrated to kr.canon (Canon Korea's new TLD-based domain).
The old CanonGallery.aspx path (plan candidates) never existed; the exhibition list
was always at /canongallery on the .co.kr site and is now at the same path on kr.canon.

Venue (from /canongallery/introduce, verified 2026-05-28):
  Name   : 캐논 갤러리
  Address: 서울특별시 강남구 봉은사로 217 캐논플렉스 지하 1층 (9호선 언주역 4번 출구)
  Hours  : 11:00–20:00 (명절 휴무), 관람료 무료
"""

from __future__ import annotations

import html
import re
import time
from collections.abc import Iterable

import httpx
from selectolax.parser import HTMLParser
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

from crawler.models import RawExhibition, SourceName
from crawler.sources.base import register_source

_BASE_URL = "https://kr.canon"
_LIST_URL = f"{_BASE_URL}/canongallery/list/ajax"
_USER_AGENT = "PhotoExhibitionCrawler/0.1 (+contact@example.com)"

_VENUE_NAME = "캐논 갤러리"
_VENUE_REGION = "서울"
_VENUE_ADDRESS = "서울특별시 강남구 봉은사로 217 캐논플렉스 지하 1층"

_PAGE_UNIT = 20
_RE_TOTAL_PAGES = re.compile(r"totalPageCount\s*=\s*(\d+)")


class CanonGalleryExtractor:
    name = SourceName.CANON_GALLERY

    def __init__(
        self,
        max_pages: int = 20,
        delay_s: float = 1.0,
        timeout_s: float = 20.0,
    ) -> None:
        self.max_pages = max_pages
        self.delay_s = delay_s
        self._client = httpx.Client(
            timeout=timeout_s,
            headers={
                "User-Agent": _USER_AGENT,
                "X-Requested-With": "XMLHttpRequest",
                "Referer": f"{_BASE_URL}/canongallery",
            },
            follow_redirects=True,
        )

    @retry(
        retry=retry_if_exception_type(httpx.TransportError),
        wait=wait_exponential(multiplier=1, min=1, max=16),
        stop=stop_after_attempt(3),
        reraise=True,
    )
    def _post(self, page: int) -> str:
        r = self._client.post(
            _LIST_URL,
            data={"pageUnit": str(_PAGE_UNIT), "pageIndex": str(page)},
        )
        r.raise_for_status()
        return r.text

    def crawl(self) -> Iterable[RawExhibition]:
        seen: set[str] = set()
        total_pages: int | None = None

        for page_num in range(1, self.max_pages + 1):
            fragment = self._post(page_num)

            # Parse total page count from first response
            if total_pages is None:
                m = _RE_TOTAL_PAGES.search(fragment)
                if m:
                    total_pages = int(m.group(1))

            cards = _extract_cards(fragment)
            if not cards:
                return

            for c in cards:
                card_url = c["source_url"]
                if card_url in seen:
                    continue
                seen.add(card_url)
                yield RawExhibition(
                    source=SourceName.CANON_GALLERY,
                    source_url=card_url,
                    raw={k: v for k, v in c.items() if k != "source_url"},
                )

            if total_pages is not None and page_num >= total_pages:
                return

            if self.delay_s > 0:
                time.sleep(self.delay_s)


def _extract_cards(fragment: str) -> list[dict]:
    """Parse a Canon Gallery AJAX response fragment into card dicts.

    Returns dicts with keys: source_url, title, date_range, poster_image_url,
    venue_name, venue_region, venue_address.
    """
    doc = HTMLParser(fragment)
    cards: list[dict] = []

    for a in doc.css("a.masonry-item"):
        href = a.attributes.get("href", "")
        if not href or "gllyDispSeq" not in href:
            continue

        # Ensure absolute URL
        if href.startswith("/"):
            source_url = f"{_BASE_URL}{href}"
        else:
            source_url = href

        # Title — <div class="txt"><p>…</p></div>
        title_el = a.css_first("div.txt p")
        raw_title = html.unescape(title_el.text(strip=True)) if title_el else ""
        if not raw_title:
            continue

        # Date range — <div class="info-list"><p>…</p></div>
        date_el = a.css_first("div.info-list p")
        date_range: str | None = date_el.text(strip=True) if date_el else None

        # Poster image — <div class="img"><img src="…"></div>
        img_el = a.css_first("div.img img")
        poster: str | None = None
        if img_el:
            src = img_el.attributes.get("src", "")
            if src:
                poster = f"https:{src}" if src.startswith("//") else src

        cards.append({
            "source_url": source_url,
            "title": raw_title,
            "date_range": date_range or None,
            "poster_image_url": poster or None,
            "venue_name": _VENUE_NAME,
            "venue_region": _VENUE_REGION,
            "venue_address": _VENUE_ADDRESS,
        })

    return cards


register_source(SourceName.CANON_GALLERY, CanonGalleryExtractor)
