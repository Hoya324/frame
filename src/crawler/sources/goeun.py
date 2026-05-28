"""고은사진미술관 (Goeun Museum of Photography, goeunmuseum.kr) — list extractor.

Strategy: Walk paginated GET requests to
  /bbs/board.php?bo_table=exhibition&page=N  (1-indexed).
The site uses a single gnuboard board for all exhibitions (current + past).
Current exhibitions appear on page 1 near the top.
Stop when a page returns no cards or max_pages is reached.

The site uses a self-signed TLS certificate; we use the certifi CA bundle which
works correctly in practice (the chain resolves via a trusted intermediate).

Card structure (verified 2026-05-28, goeunmuseum.kr):
  <div class="list-item">
    <div class="imgframe">
      <div class="img-item">
        <a href="...?bo_table=exhibition&wr_id=NNN&page=P&proc=">
          <img src="...">
        </a>
      </div>
    </div>
    <a href="...?bo_table=exhibition&wr_id=NNN&page=P&proc=">
      <div class="txt_wrap">
        <h4>서브타이틀 (may be empty)</h4>
        <h2 class="notranslate">전시 제목</h2>
        <div class="list-details text-muted">
          <p>작가명</p>
          <p>YYYY/MM/DD - YYYY/MM/DD</p>
        </div>
      </div>
    </a>
  </div>

Domain note: the plan referenced goeunmuseum.org which is a misconfigured server;
the real site is goeunmuseum.kr.
"""

from __future__ import annotations

import ssl
import time
from collections.abc import Iterable
from urllib.parse import parse_qs, urljoin, urlparse

import certifi
import httpx
from selectolax.parser import HTMLParser
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

from crawler.models import RawExhibition, SourceName
from crawler.sources.base import register_source

_BASE_URL = "https://www.goeunmuseum.kr"
_LIST_URL = f"{_BASE_URL}/bbs/board.php"
_BO_TABLE = "exhibition"
_USER_AGENT = "PhotoExhibitionCrawler/0.1 (+contact@example.com)"

_VENUE_NAME = "고은사진미술관"
_VENUE_REGION = "부산"
_VENUE_ADDRESS = "부산광역시 해운대구 해운대로 452번길 16"


def _canonical_url(wr_id: str) -> str:
    """Return a stable canonical URL using only bo_table + wr_id."""
    return f"{_BASE_URL}/bbs/board.php?bo_table={_BO_TABLE}&wr_id={wr_id}"


class GoeunExtractor:
    name = SourceName.GOEUN

    def __init__(
        self,
        max_pages: int = 10,
        delay_s: float = 1.0,
        timeout_s: float = 20.0,
    ) -> None:
        self.max_pages = max_pages
        self.delay_s = delay_s
        ssl_ctx = ssl.create_default_context(cafile=certifi.where())
        self._client = httpx.Client(
            timeout=timeout_s,
            headers={"User-Agent": _USER_AGENT},
            follow_redirects=True,
            verify=ssl_ctx,
        )

    @retry(
        retry=retry_if_exception_type(httpx.TransportError),
        wait=wait_exponential(multiplier=1, min=1, max=16),
        stop=stop_after_attempt(3),
        reraise=True,
    )
    def _get(self, page: int) -> str:
        r = self._client.get(
            _LIST_URL,
            params={"bo_table": _BO_TABLE, "page": str(page)},
        )
        r.raise_for_status()
        return r.text

    def crawl(self) -> Iterable[RawExhibition]:
        seen: set[str] = set()
        for page_num in range(1, self.max_pages + 1):
            html = self._get(page_num)
            cards = _extract_cards(html)
            if not cards:
                return

            for c in cards:
                url = c["source_url"]
                if url in seen:
                    continue
                seen.add(url)
                yield RawExhibition(
                    source=SourceName.GOEUN,
                    source_url=url,
                    raw={k: v for k, v in c.items() if k != "source_url"},
                )

            if self.delay_s > 0:
                time.sleep(self.delay_s)


def _extract_wr_id(href: str) -> str | None:
    """Extract wr_id query parameter from a gnuboard exhibition URL."""
    parsed = urlparse(href)
    qs = parse_qs(parsed.query)
    ids = qs.get("wr_id", [])
    return ids[0] if ids else None


def _extract_cards(html: str) -> list[dict]:
    """Parse an exhibition listing page into card dicts.

    Returns dicts with keys: source_url, title, artists, venue_name,
    venue_region, venue_address, date_range, poster_image_url.
    """
    doc = HTMLParser(html)
    cards: list[dict] = []

    for item in doc.css("div.list-item"):
        # Prefer the image-frame anchor for the href (contains wr_id)
        a = item.css_first("div.imgframe a[href]")
        if not a:
            a = item.css_first("a[href]")
        href = a.attributes.get("href") if a else None
        if not href:
            continue

        # Canonicalize URL to stable bo_table + wr_id form
        wr_id = _extract_wr_id(href)
        if not wr_id:
            continue
        url = _canonical_url(wr_id)

        # Title: h2.notranslate
        h2 = item.css_first("h2.notranslate")
        title = h2.text(strip=True) if h2 else ""
        if not title:
            continue

        # Date range + artist: first two <p> inside .list-details
        ps = item.css("div.list-details.text-muted p")
        artist: str | None = ps[0].text(strip=True) if len(ps) > 0 else None
        date_range: str | None = ps[1].text(strip=True) if len(ps) > 1 else None

        # Poster image
        img = item.css_first("img")
        poster: str | None = img.attributes.get("src") if img else None
        if poster and not poster.startswith("http"):
            poster = urljoin(_BASE_URL, poster)

        cards.append({
            "source_url": url,
            "title": title,
            "artists": artist or None,
            "venue_name": _VENUE_NAME,
            "venue_region": _VENUE_REGION,
            "venue_address": _VENUE_ADDRESS,
            "date_range": date_range or None,
            "poster_image_url": poster or None,
        })

    return cards


register_source(SourceName.GOEUN, GoeunExtractor)
