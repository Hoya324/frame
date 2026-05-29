"""공근혜갤러리 K.O.N.G Gallery (konggallery.com) — exhibition list extractor.

Strategy: Two-phase crawl.
  Phase 1 — Walk the past-exhibitions grid at /EXHIBITIONS_PAST (single page).
             Each grid cell is a `div._item.item_gallary` containing an
             `a.item_container` whose `href` is the detail-page slug and whose
             `div.img_wrap[data-src]` holds the poster thumbnail URL.
  Phase 2 — Fetch each detail page.  The first non-empty `div[id^="text_"]`
             inside `.section_wrap` contains paragraphs in this order:
               p[0]: Korean title
               p[1]: English title (or date range when only two paras present)
               p[-1]: date range

Limitation — current / upcoming exhibitions are NOT captured.
  The /CURRENT and /UPCOMING pages on konggallery.com are JS-rendered
  placeholders: server-side HTML contains exactly one empty `text_*` widget
  (no `<p>` children) and a single image widget linking to /MAIN
  (verified 2026-05-28).  No title / artist / date appears anywhere in the
  static markup, and /UPCOMING has zero `<main>` content sections at all.
  Only /EXHIBITIONS_PAST produces a server-rendered grid with extractable
  detail-page links.  This means an exhibition will only enter the pipeline
  once it ages into the PAST archive.
  TODO: revisit with a Playwright fallback for /CURRENT and /UPCOMING when a
  headless-browser pipeline lands, so ongoing shows are captured in real time.

Domain note: The plan listed gallerykong.com / kong-gallery.com.  Those domains
are defunct or unrelated as of 2026-05-28.  The live site is konggallery.com
(redirects from www.konggallery.com).

Venue address from site footer (verified 2026-05-28):
  #38, Samcheongro 7 gil, Jongnogu Seoul, KOREA
  = 서울특별시 종로구 삼청로7길 38
"""

from __future__ import annotations

import time
from collections.abc import Iterable
from urllib.parse import urljoin

import httpx
from selectolax.parser import HTMLParser
from tenacity import retry, retry_if_exception, stop_after_attempt, wait_exponential

from crawler.models import RawExhibition, SourceName
from crawler.sources.base import register_source

_BASE_URL = "https://www.konggallery.com"
_LIST_URL = f"{_BASE_URL}/EXHIBITIONS_PAST"
_USER_AGENT = "PhotoExhibitionCrawler/0.1 (+contact@example.com)"

# Statuses we treat as transient. konggallery.com is on Wix, which
# occasionally serves 403/429 to data-center IPs (intermittently
# observed from GitHub Actions runners). Retrying after a backoff
# usually clears it.
_RETRYABLE_HTTP_STATUSES = frozenset({403, 429, 500, 502, 503, 504})


def _should_retry(exc: BaseException) -> bool:
    if isinstance(exc, httpx.TransportError):
        return True
    if isinstance(exc, httpx.HTTPStatusError):
        return exc.response.status_code in _RETRYABLE_HTTP_STATUSES
    return False

_VENUE_NAME = "공근혜갤러리"
_VENUE_REGION = "서울"
_VENUE_ADDRESS = "서울특별시 종로구 삼청로7길 38"


class GalleryKongExtractor:
    name = SourceName.GALLERY_KONG

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
        retry=retry_if_exception(_should_retry),
        wait=wait_exponential(multiplier=2, min=2, max=60),
        stop=stop_after_attempt(4),
        reraise=True,
    )
    def _get(self, url: str) -> str:
        r = self._client.get(url)
        r.raise_for_status()
        return r.text

    def crawl(self) -> Iterable[RawExhibition]:
        list_html = self._get(_LIST_URL)
        list_cards = _extract_list_cards(list_html)
        if not list_cards:
            return

        seen: set[str] = set()
        for card in list_cards:
            detail_url = card["source_url"]
            if detail_url in seen:
                continue
            seen.add(detail_url)

            if self.delay_s > 0:
                time.sleep(self.delay_s)

            try:
                detail_html = self._get(detail_url)
            except httpx.HTTPStatusError:
                continue

            info = _extract_detail(detail_html)
            if not info.get("title"):
                continue

            yield RawExhibition(
                source=SourceName.GALLERY_KONG,
                source_url=detail_url,
                raw={
                    "title": info["title"],
                    "venue_name": _VENUE_NAME,
                    "venue_region": _VENUE_REGION,
                    "venue_address": _VENUE_ADDRESS,
                    "date_range": info.get("date_range") or None,
                    "poster_image_url": card.get("poster_image_url") or None,
                },
            )


def _extract_list_cards(html: str) -> list[dict]:
    """Parse the EXHIBITIONS_PAST grid and return one dict per exhibition.

    Keys: source_url, poster_image_url.
    """
    doc = HTMLParser(html)
    cards: list[dict] = []

    for item in doc.css("div._item.item_gallary"):
        a = item.css_first("a.item_container._item_container")
        if not a:
            continue
        href = a.attributes.get("href", "")
        if not href or "javascript" in href or href == "#":
            continue

        detail_url = urljoin(_BASE_URL, href)

        # Poster thumbnail from data-src on img_wrap div
        img_div = a.css_first("div.img_wrap._img_wrap")
        poster: str | None = None
        if img_div:
            poster = img_div.attributes.get("data-src") or None
            if not poster:
                # Fall back to data-bg which may have url(...) wrapper
                bg = img_div.attributes.get("data-bg", "")
                if bg:
                    poster = bg.replace("url(", "").replace(")", "").strip() or None

        cards.append({"source_url": detail_url, "poster_image_url": poster})

    return cards


def _extract_detail(html: str) -> dict:
    """Parse an exhibition detail page.

    Returns dict with keys: title (Korean), date_range.
    The first non-empty `div[id^="text_"]` contains <p> elements:
      - 3+ paras: p[0]=Korean title, p[1]=English title, p[-1]=date range
      - 2 paras:  p[0]=Korean title, p[1]=date range
    """
    doc = HTMLParser(html)

    for div in doc.css("[id^='text_']"):
        paras = [
            p.text(strip=True).replace("\xa0", " ").strip()
            for p in div.css("p")
        ]
        paras = [p for p in paras if p]
        if not paras:
            continue

        title = paras[0]
        date_range: str | None = None
        if len(paras) >= 2:
            date_range = paras[-1]
            # Avoid using the Korean title itself as the date range when len==1
            # (edge case: single para has both title+date concatenated)

        return {"title": title, "date_range": date_range}

    return {}


register_source(SourceName.GALLERY_KONG, GalleryKongExtractor)
