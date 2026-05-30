"""뮤지엄한미 (Museum Hanmi, museumhanmi.or.kr) — exhibition list extractor.

Strategy: Walk paginated GET requests to /exhibition/?pgs=N (1-indexed).
Each page renders server-side WordPress HTML with exhibition cards.
The site has two physical branches:
  - "삼청" (main branch, Samcheong-dong)
  - "삼청별관" (annex, Samcheong annex)
Each card includes the branch name; we use it as venue_name so the
entity resolver can treat them as separate venues.

Card structure (verified 2026-05-28):
  <a href="https://museumhanmi.or.kr/post_exhibition/..." class="item row gap-1r">
    <div class="thumb">
      <img src="https://museumhanmi.or.kr/wp-content/uploads/..." />
    </div>
    <div class="meta row gap-16">
      <div class="stat">
        <h6 class="bold">삼청</h6>         ← branch
        <h6 class="bold">진행중</h6>        ← status (optional)
      </div>
      <h4>《전시 제목》</h4>               ← title
      <h6 class="text-sub single-line">YYYY.MM.DD. 요일 ~ YYYY.MM.DD. 요일</h6>
    </div>
  </a>

Pagination: /exhibition/?pgs=1, ?pgs=2, ...
Stop when a page returns no cards.

Robots/manners: No robots.txt disallow for /exhibition/. Default 1 s delay.
"""

from __future__ import annotations

import time
from collections.abc import Iterable

import httpx
from selectolax.parser import HTMLParser
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

from crawler.models import RawExhibition, SourceName
from crawler.sources._detail import MIN_DESCRIPTION_LEN, meta_description, paragraphs_text
from crawler.sources.base import register_source

_BASE_URL = "https://museumhanmi.or.kr"
_LIST_URL = f"{_BASE_URL}/exhibition/"
_USER_AGENT = "PhotoExhibitionCrawler/0.1 (+contact@example.com)"


class MuseumHanmiExtractor:
    name = SourceName.MUSEUM_HANMI

    def __init__(
        self,
        max_pages: int = 20,
        delay_s: float = 1.0,
        timeout_s: float = 20.0,
        with_details: bool = True,
    ) -> None:
        self.max_pages = max_pages
        self.delay_s = delay_s
        self.with_details = with_details
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
        r = self._client.get(_LIST_URL, params={"pgs": str(page)})
        r.raise_for_status()
        return r.text

    @retry(
        retry=retry_if_exception_type(httpx.TransportError),
        wait=wait_exponential(multiplier=1, min=1, max=16),
        stop=stop_after_attempt(3),
        reraise=True,
    )
    def _get_url(self, url: str) -> str:
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
                payload = {k: v for k, v in c.items() if k != "source_url"}
                if self.with_details:
                    try:
                        payload.update(_parse_detail(self._get_url(url)))
                    except Exception:  # noqa: BLE001
                        # Partial data beats dropping the row; list fields stay.
                        pass
                    if self.delay_s > 0:
                        time.sleep(self.delay_s)
                yield RawExhibition(
                    source=SourceName.MUSEUM_HANMI,
                    source_url=url,
                    raw=payload,
                )

            if self.delay_s > 0:
                time.sleep(self.delay_s)


def _extract_cards(html: str) -> list[dict]:
    """Parse an exhibition listing page into card dicts.

    Returns dicts with keys: source_url, title, venue_name, date_range,
    poster_image_url.
    """
    doc = HTMLParser(html)
    cards: list[dict] = []

    for a in doc.css("a.item.row.gap-1r"):
        href = a.attributes.get("href") or ""
        if not href or "/post_exhibition/" not in href:
            continue

        # Poster image
        img = a.css_first("img")
        poster: str | None = img.attributes.get("src") if img else None

        # Branch name (first h6.bold)
        h6_bolds = a.css("h6.bold")
        venue_name: str | None = h6_bolds[0].text(strip=True) if h6_bolds else None

        # Title (h4)
        title_el = a.css_first("h4")
        title = title_el.text(strip=True) if title_el else ""
        if not title:
            continue

        # Date range (h6.text-sub)
        date_el = a.css_first("h6.text-sub")
        date_range: str | None = date_el.text(strip=True) if date_el else None

        cards.append({
            "source_url": href,
            "title": title,
            "venue_name": venue_name or None,
            "date_range": date_range or None,
            "poster_image_url": poster or None,
        })

    return cards


def _parse_detail(html: str) -> dict:
    """Pull the exhibition blurb from a 뮤지엄한미 detail page.

    The prose sits in `div.col-2.detail`, whose first `.row` child holds the
    title/date line and a later `.row` holds the paragraphs. We pick the row
    with the most `<p>` text so the choice survives layout-class churn.
    """
    doc = HTMLParser(html)
    detail = doc.css_first("div.col-2.detail")
    best = ""
    if detail is not None:
        for row in detail.css("div.row"):
            text = paragraphs_text(row)
            if len(text) > len(best):
                best = text

    if len(best) < MIN_DESCRIPTION_LEN:
        best = meta_description(doc) or best
    return {"description": best} if len(best) >= MIN_DESCRIPTION_LEN else {}


# Register on import
register_source(SourceName.MUSEUM_HANMI, MuseumHanmiExtractor)
