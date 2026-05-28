"""일우스페이스 (Ilwoo Space, ilwoo.org) — exhibition list extractor.

Strategy: Walk paginated GET requests to /default/m02/p03.php (BBS-style board).
The site renders server-side HTML with exhibition rows in a table.  Each row is
a <tr> element with an onclick attribute and an inner anchor link to the detail
page (com_board_basic=read_form).  Pagination follows com_board_page=N (1-indexed;
omit or empty string for page 1).  Stop when a page returns no board rows.

The site is served with EUC-KR encoding; httpx returns bytes which we decode
explicitly.

Card structure (verified 2026-05-28, www.ilwoo.org):
  <tr onclick="location.href='/default/m02/p03.php?com_board_basic=read_form
               &com_board_idx=93&&...'" style='cursor:pointer;'>
    <td class="bbsno">89</td>
    <td class="bbsnewf5">
      <a href=""><a href="/default/m02/p03.php?com_board_basic=read_form
                      &com_board_idx=93&&...">전시 제목</a></a>
    </td>
    <td class="bbsetc_add1">2026.5. 1 ~ 2026.5.31</td>
  </tr>

Source URL is normalised to four canonical query params
(com_board_basic, com_board_idx, com_board_page, com_board_id) to strip
the duplicate & redundant params that the board software emits.

Domain note: The plan listed ilwoospace.org / ilwoospace.com / ilwoospace.co.kr
— all of which are unresolvable DNS names as of 2026-05-28.  The gallery's
parent foundation (일우재단, Ilwoo Foundation) runs the live site at
  https://www.ilwoo.org/default/m02/p03.php
which hosts the 일우스페이스 exhibition board.  Verified 2026-05-28.

Venue address from site footer (verified 2026-05-28):
  서울시 중구 서소문로 117 대한항공 빌딩 6층
"""

from __future__ import annotations

import time
from collections.abc import Iterable
from urllib.parse import parse_qs, urlencode, urljoin, urlparse, urlunparse

import httpx
from selectolax.parser import HTMLParser
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

from crawler.models import RawExhibition, SourceName
from crawler.sources.base import register_source

_BASE_URL = "https://www.ilwoo.org"
_LIST_URL = f"{_BASE_URL}/default/m02/p03.php"
_USER_AGENT = "PhotoExhibitionCrawler/0.1 (+contact@example.com)"

_VENUE_NAME = "일우스페이스"
_VENUE_REGION = "서울"
_VENUE_ADDRESS = "서울시 중구 서소문로 117 대한항공 빌딩 6층"

_BOARD_ID = "10"


def _build_list_url(page: int) -> str:
    """Return the list URL for the given page number (1-indexed)."""
    if page == 1:
        return _LIST_URL
    params = {
        "com_board_page": str(page),
        "com_board_id": _BOARD_ID,
    }
    return f"{_LIST_URL}?{urlencode(params)}"


def _normalise_detail_url(href: str) -> str:
    """Strip duplicate/redundant query params from a detail-page href.

    The board software emits things like:
      /default/m02/p03.php?com_board_basic=read_form&com_board_idx=93
        &&com_board_search_code=&...&&com_board_id=10&&com_board_id=10

    We keep only the four params that uniquely identify the post.
    """
    full = urljoin(_BASE_URL, href)
    parsed = urlparse(full)
    qs = parse_qs(parsed.query, keep_blank_values=True)
    canonical = {
        "com_board_basic": qs.get("com_board_basic", ["read_form"])[0],
        "com_board_idx": qs.get("com_board_idx", [""])[0],
        "com_board_page": qs.get("com_board_page", [""])[0],
        "com_board_id": qs.get("com_board_id", [_BOARD_ID])[0],
    }
    return urlunparse(parsed._replace(query=urlencode(canonical)))


class IlwooSpaceExtractor:
    name = SourceName.ILWOO_SPACE

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
        # The live site is served as EUC-KR.  Use the response encoding reported
        # in the Content-Type header so that mocked responses (which use UTF-8)
        # are also decoded correctly.
        encoding = r.encoding or "euc-kr"
        return r.content.decode(encoding, errors="replace")

    def crawl(self) -> Iterable[RawExhibition]:
        seen: set[str] = set()
        for page_num in range(1, self.max_pages + 1):
            url = _build_list_url(page_num)
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
                    source=SourceName.ILWOO_SPACE,
                    source_url=card_url,
                    raw={k: v for k, v in c.items() if k != "source_url"},
                )

            if self.delay_s > 0:
                time.sleep(self.delay_s)


def _extract_cards(html: str) -> list[dict]:
    """Parse an Ilwoo Space exhibition board page into card dicts.

    Returns dicts with keys: source_url, title, venue_name, venue_region,
    venue_address, date_range.
    """
    doc = HTMLParser(html)
    cards: list[dict] = []

    for tr in doc.css("tr"):
        onclick = tr.attributes.get("onclick", "")
        if "read_form" not in onclick or "com_board_idx" not in onclick:
            continue

        # Detail URL — the inner anchor with read_form href
        all_a = tr.css("a[href*='read_form']")
        if not all_a:
            continue
        # The board emits nested <a href=""><a href="...">  — take the last one
        # which has the real href, or the first href that is non-empty.
        href = ""
        for a in reversed(all_a):
            candidate = a.attributes.get("href", "")
            if candidate and "com_board_idx" in candidate:
                href = candidate
                break
        if not href:
            continue

        source_url = _normalise_detail_url(href)

        # Title text
        title_td = tr.css_first("td.bbsnewf5")
        title = title_td.text(strip=True) if title_td else ""
        if not title:
            continue
        # Remove trailing ".." truncation marker added by the board
        if title.endswith(".."):
            title = title[:-2].rstrip()

        # Date range
        date_td = tr.css_first("td.bbsetc_add1")
        date_range: str | None = date_td.text(strip=True) if date_td else None

        cards.append({
            "source_url": source_url,
            "title": title,
            "venue_name": _VENUE_NAME,
            "venue_region": _VENUE_REGION,
            "venue_address": _VENUE_ADDRESS,
            "date_range": date_range or None,
        })

    return cards


register_source(SourceName.ILWOO_SPACE, IlwooSpaceExtractor)
