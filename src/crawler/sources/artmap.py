"""Artmap (art-map.co.kr) — data-endpoint extractor.

Strategy: walk paginated POST batches from /data/new_exhibition.php, parse each
card's HTML fragment, yield RawExhibition with list-page fields. Detail-page
enrichment is left for v1.5.

NOTE ON ARCHITECTURE: The Artmap list page (new_list.php) is a JavaScript shell
that injects cards via AJAX. The real data comes from:
  POST https://art-map.co.kr/data/new_exhibition.php
with form params: start (offset, +4 each batch), wrap (batch number, +1),
type, area, cate, od, v_cnt, online.

Card structure (verified 2026-05-28):
  <a href='view.php?idx=NNNN'>
    <img src='https://art-map.co.kr/art-map/public/...'>
    <div class='new_exh_list'>
      <span id='ttl_N'>TITLE</span>
      <span>VENUE_NAME/REGION</span>
      <span>YYYY.MM.DD ~ YYYY.MM.DD</span>
      <span class='mck'>...</span>   ← hidden checkbox, skip
    </div>
  </a>
"""

from __future__ import annotations

import re
import time
from typing import Iterable

import httpx
from selectolax.parser import HTMLParser
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

from crawler.models import RawExhibition, SourceName
from crawler.sources.base import register_source


_DATA_URL = "https://art-map.co.kr/data/new_exhibition.php"
_BASE = "https://art-map.co.kr"
_USER_AGENT = "PhotoExhibitionCrawler/0.1 (+contact@example.com)"
_DETAIL_RE = re.compile(r"view\.php\?idx=(\d+)")
_BATCH_SIZE = 4  # server always returns 4 cards per batch


class ArtmapExtractor:
    name = SourceName.ARTMAP

    def __init__(
        self,
        max_batches: int = 20,
        delay_s: float = 1.0,
        timeout_s: float = 20.0,
    ) -> None:
        self.max_batches = max_batches
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
    def _post(self, start: int, wrap: int) -> str:
        r = self._client.post(
            _DATA_URL,
            data={
                "start": str(start),
                "wrap": str(wrap),
                "type": "ing",
                "area": "0",
                "cate": "",
                "od": "2",
                "v_cnt": "0",
                "online": "0",
            },
        )
        r.raise_for_status()
        return r.text

    def crawl(self) -> Iterable[RawExhibition]:
        seen: set[str] = set()
        for batch_num in range(1, self.max_batches + 1):
            start = (batch_num - 1) * _BATCH_SIZE
            html = self._post(start=start, wrap=batch_num)

            # Server returns the literal string "end" when exhausted
            if html.strip() == "end":
                return

            cards = _extract_cards(html)
            if not cards:
                return

            for c in cards:
                url = c["source_url"]
                if url in seen:
                    continue
                seen.add(url)
                yield RawExhibition(
                    source=SourceName.ARTMAP,
                    source_url=url,
                    raw={k: v for k, v in c.items() if k != "source_url"},
                )

            if self.delay_s > 0:
                time.sleep(self.delay_s)


def _extract_cards(html: str) -> list[dict]:
    """Parse a batch HTML fragment into card dicts.

    Returns dicts with keys: source_url, title, venue_name, venue_region,
    date_range, poster_image_url.
    """
    doc = HTMLParser(html)
    cards: list[dict] = []

    for a in doc.css("a"):
        href = a.attributes.get("href") or ""
        m = _DETAIL_RE.search(href)
        if not m:
            continue
        idx = m.group(1)
        source_url = f"{_BASE}/exhibition/view.php?idx={idx}"

        # Poster image
        img = a.css_first("img")
        poster: str | None = img.attributes.get("src") if img else None
        if poster and not poster.startswith("http"):
            poster = _BASE + ("" if poster.startswith("/") else "/") + poster

        # Text fields from .new_exh_list spans
        # span[0]: title (has id='ttl_N')
        # span[1]: venue/region combined
        # span[2]: date range
        # span[3]: map checkbox (.mck) — skip
        spans = a.css(".new_exh_list span")

        title = spans[0].text(strip=True) if spans else ""
        if not title:
            continue

        venue_combined = spans[1].text(strip=True) if len(spans) > 1 else ""
        date_range = spans[2].text(strip=True) if len(spans) > 2 else ""

        venue_name: str | None = None
        venue_region: str | None = None
        if venue_combined:
            name_part, _, region_part = venue_combined.partition("/")
            venue_name = name_part.strip() or None
            venue_region = region_part.strip() or None

        cards.append({
            "source_url": source_url,
            "title": title,
            "venue_name": venue_name,
            "venue_region": venue_region,
            "date_range": date_range or None,
            "poster_image_url": poster or None,
        })

    return cards


# Register on import
register_source(SourceName.ARTMAP, ArtmapExtractor)
