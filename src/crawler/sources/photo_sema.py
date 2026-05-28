"""Photo SeMA (서울시립 사진미술관) — static-HTML extractor.

Strategy: GET the SeMA whatson/landing page filtered to branch ORG51
(서울시립 사진미술관). Parse each exhibition card from the server-rendered HTML
and yield only exhibitions hosted at Photo SeMA.

URL pattern:
  GET https://sema.seoul.go.kr/kr/whatson/landing
    ?whatsonMenuDivList=EX
    &exPlace=ORG51            ← Photo SeMA branch filter
    &whatChoice2=N&whatChoice3=N&whatChoice4=N&whatChoice5=N
    &whenType=FROM_TODAY
    &currentPage=<N>          ← 1-based page number

Card structure (verified 2026-05-28):
  <div id="dv_<IDX>" class="... viewLink ..." data-idx="<IDX>"
       data-ex-menu-div="EXM01">
    <a href="javascript:;" class="o_figure">
      <div class="o_thumb">
        <img src="/common/imgFileView?FILE_ID=<ID>">
      </div>
      <div class="t-metadata o_figcaption">
        <strong class="o_h1">TITLE</strong>
        <span class="o_h2 epEcPlaceNm app-none">
          ...  VENUE_NAME,  ...   ← text nodes, many blank siblings
        </span>
        <span class="o_h3">
          DATE_RANGE            ← format: YYYY/MM/DD~YYYY/MM/DD
        </span>
      </div>
    </a>
  </div>

Detail URL:
  https://sema.seoul.go.kr/kr/whatson/exhibition/detail?exNo=<IDX>

Pagination: page parameter is &currentPage=N (appended to URL).
Server returns an empty card container when the page is beyond the last.

Branch filtering: The exPlace=ORG51 URL parameter pre-filters to Photo SeMA
on the server side. As a secondary defence, we also check that each card's
venue text contains "사진미술관" and skip non-matching cards.

SeMA branch codes (for reference):
  ORG60 — 서울시립미술관 (전체)
  ORG01 — 서울시립미술관 서소문본관
  ORG08 — 서울시립 북서울미술관
  ORG50 — 서울시립 서서울미술관
  ORG03 — 서울시립 남서울미술관
  ORG51 — 서울시립 사진미술관 ← this extractor
  ORG52 — (reserve code next to ORG51)
  ORG04 — 난지미술창작스튜디오
  ORG12 — SeMA 벙커
  ORG11 — SeMA 창고
  ORG10 — SeMA 백남준기념관
  ORG61 — 서울시립 서서울미술관 관련시설

Robots: No robots.txt restriction found; crawl respectfully (1 s delay).
"""

from __future__ import annotations

import re
import time
from collections.abc import Iterable

import httpx
from selectolax.parser import HTMLParser
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

from crawler.models import RawExhibition, SourceName
from crawler.sources.base import register_source

_BASE = "https://sema.seoul.go.kr"
_LIST_URL = (
    "https://sema.seoul.go.kr/kr/whatson/landing"
    "?whatsonMenuDivList=EX&exPlace=ORG51"
    "&whatChoice2=N&whatChoice3=N&whatChoice4=N&whatChoice5=N"
    "&whenType=FROM_TODAY"
)
_DETAIL_BASE = "https://sema.seoul.go.kr/kr/whatson/exhibition/detail"
_USER_AGENT = "PhotoExhibitionCrawler/0.1 (+contact@example.com)"

# Substring that appears in the venue text for Photo SeMA cards.
# Used as a secondary branch filter in case ORG51 URL parameter is ignored.
_PHOTO_SEMA_KEYWORD = "사진미술관"


class PhotoSemaExtractor:
    name = SourceName.PHOTO_SEMA

    def __init__(
        self,
        max_pages: int = 10,
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
    def _get(self, page: int) -> str:
        url = _LIST_URL
        if page > 1:
            url = f"{url}&currentPage={page}"
        r = self._client.get(url)
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
                    source=SourceName.PHOTO_SEMA,
                    source_url=url,
                    raw={k: v for k, v in c.items() if k != "source_url"},
                )

            if self.delay_s > 0:
                time.sleep(self.delay_s)


def _extract_cards(html: str) -> list[dict]:
    """Parse a page HTML into card dicts.

    Returns dicts with keys: source_url, title, venue_name, date_range,
    poster_image_url.

    Only Photo SeMA cards are returned (venue contains "사진미술관").
    """
    doc = HTMLParser(html)
    cards: list[dict] = []

    for div in doc.css("div.viewLink"):
        idx = div.attributes.get("data-idx")
        ex_menu_div = div.attributes.get("data-ex-menu-div", "")
        # Only process standard exhibitions (not biennale/outdoor sub-types)
        if not idx or ex_menu_div != "EXM01":
            continue

        source_url = f"{_DETAIL_BASE}?exNo={idx}"

        # Poster image
        img = div.css_first("img")
        poster: str | None = None
        if img:
            src = img.attributes.get("src", "")
            if src and not src.startswith("http"):
                poster = _BASE + src
            elif src:
                poster = src

        # Title
        title_el = div.css_first("strong.o_h1")
        title = title_el.text(strip=True) if title_el else ""
        if not title:
            continue

        # Venue — .epEcPlaceNm contains many blank child spans;
        # we collect all non-empty text nodes and join them.
        venue_el = div.css_first("span.epEcPlaceNm")
        venue_name: str | None = None
        if venue_el:
            venue_raw = venue_el.text(strip=True)
            # Strip trailing comma / whitespace
            venue_cleaned = re.sub(r",\s*$", "", venue_raw).strip()
            if venue_cleaned:
                venue_name = venue_cleaned

        # Branch filter: only yield Photo SeMA cards
        if venue_name is None or _PHOTO_SEMA_KEYWORD not in venue_name:
            continue

        # Date range
        date_el = div.css_first("span.o_h3")
        date_range: str | None = None
        if date_el:
            dt = date_el.text(strip=True)
            if dt:
                date_range = dt

        cards.append({
            "source_url": source_url,
            "title": title,
            "venue_name": venue_name,
            "date_range": date_range,
            "poster_image_url": poster,
        })

    return cards


# Register on import
register_source(SourceName.PHOTO_SEMA, PhotoSemaExtractor)
