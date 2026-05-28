"""갤러리 룩스 (Gallery LUX, gallerylux.net) — list extractor.

Strategy: Walk paginated GET requests to /archive/page/N/ (1-indexed).
The site uses a WordPress theme that renders all exhibitions (current + past)
as archive-style cards at /archive/.  Pagination is /archive/page/2/, etc.
Stop when a page returns no article cards or max_pages is reached.

Card structure (verified 2026-05-28, gallerylux.net):
  <article class="blog-item card-type ...">
    <a href="https://gallerylux.net/<slug>/">
      <div class="card-thumbnail">
        <img src="...">
      </div>
      <div class="entry-text-wrap">
        <h1 class="entry-title">
          <div class="title">전시 제목</div>
          <div class="artist-name">작가명</div>   ← may be absent
        </h1>
        <div class="entry-info">
          <div class="date">YYYY. M. D - M. D</div>   ← may be absent
        </div>
      </div>
    </a>
  </article>

Venue address from site footer: 62 Ogin-dong, Jongno-gu, Seoul, Korea
  (= 서울특별시 종로구 옥인동 62)

Domain note: the plan listed www.gallerylux.net which redirects to
gallerylux.net; both work.  The exhibition list URL is /archive/ (not
/exhibition/ — those paths return 404).
Verified 2026-05-28.
"""

from __future__ import annotations

import time
from collections.abc import Iterable
from urllib.parse import urljoin

import httpx
from selectolax.parser import HTMLParser
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

from crawler.models import RawExhibition, SourceName
from crawler.sources.base import register_source

_BASE_URL = "https://gallerylux.net"
_LIST_URL = f"{_BASE_URL}/archive/"
_USER_AGENT = "PhotoExhibitionCrawler/0.1 (+contact@example.com)"

_VENUE_NAME = "갤러리 룩스"
_VENUE_REGION = "서울"
_VENUE_ADDRESS = "서울특별시 종로구 옥인동 62"


class GalleryLuxExtractor:
    name = SourceName.GALLERY_LUX

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
        seen: set[str] = set()
        for page_num in range(1, self.max_pages + 1):
            if page_num == 1:
                url = _LIST_URL
            else:
                url = urljoin(_BASE_URL, f"/archive/page/{page_num}/")

            html = self._get(url)
            cards = _extract_cards(html)
            if not cards:
                return

            for c in cards:
                card_url = c["source_url"]
                if card_url in seen:
                    continue
                seen.add(card_url)
                yield RawExhibition(
                    source=SourceName.GALLERY_LUX,
                    source_url=card_url,
                    raw={k: v for k, v in c.items() if k != "source_url"},
                )

            if self.delay_s > 0:
                time.sleep(self.delay_s)


def _extract_cards(html: str) -> list[dict]:
    """Parse a Gallery LUX archive page into card dicts.

    Returns dicts with keys: source_url, title, artists, venue_name,
    venue_region, venue_address, date_range, poster_image_url.
    """
    doc = HTMLParser(html)
    cards: list[dict] = []

    for art in doc.css("article"):
        # Detail URL — first anchor inside the article
        a = art.css_first("a[href]")
        href = a.attributes.get("href", "") if a else ""
        if not href:
            continue

        # Title — div.title inside entry-title h1
        title_el = art.css_first("div.title")
        title = title_el.text(strip=True) if title_el else ""
        if not title:
            continue

        # Artist name — div.artist-name (may be absent)
        artist_el = art.css_first("div.artist-name")
        artist_text = artist_el.text(strip=True) if artist_el else ""

        # Date range — div.date inside entry-info (may be absent)
        date_el = art.css_first("div.date")
        date_range: str | None = date_el.text(strip=True) if date_el else None

        # Poster image — first img in the card-thumbnail div
        img = art.css_first("div.card-thumbnail img")
        if not img:
            img = art.css_first("img")
        poster: str | None = img.attributes.get("src") if img else None
        if poster and not poster.startswith("http"):
            poster = urljoin(_BASE_URL, poster)

        cards.append({
            "source_url": href,
            "title": title,
            "artists": [artist_text] if artist_text else [],
            "venue_name": _VENUE_NAME,
            "venue_region": _VENUE_REGION,
            "venue_address": _VENUE_ADDRESS,
            "date_range": date_range or None,
            "poster_image_url": poster or None,
        })

    return cards


register_source(SourceName.GALLERY_LUX, GalleryLuxExtractor)
