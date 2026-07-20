"""서울시립미술관 통합 (SeMA, sema.seoul.go.kr) — static-HTML extractor.

Strategy (recon 2026-07-20): GET the whatson/landing page with NO branch
filter, so every SeMA branch (서소문본관, 북서울, 남서울, 서서울, 미술아카이브,
백남준을 기억하는 집, …) is covered by one crawl. The page is server-rendered
HTML with the same `div.viewLink` cards the branch-filtered photo_sema
extractor parses.

URL pattern:
  GET https://sema.seoul.go.kr/kr/whatson/landing
    ?whatsonMenuDivList=EX
    &whenType=FROM_TODAY      ← current + upcoming
    &currentPage=<N>          ← 1-based; page 1 omits the parameter

Card structure (verified 2026-07-20 — same markup as photo_sema):
  <div id="dv_<IDX>" class="... viewLink ..." data-idx="<IDX>"
       data-whatson-menu-div="EX" data-ex-menu-div="EXM01">
    <a href="javascript:;" class="o_figure">
      <div class="o_thumb"><img src="/common/imgFileView?FILE_ID=<ID>"></div>
      <div class="t-metadata o_figcaption">
        <strong class="o_h1">TITLE</strong>
        <span class="o_h2 epEcPlaceNm app-none"> VENUE_NAME, </span>
        <span class="o_h3"> YYYY/MM/DD~YYYY/MM/DD </span>
      </div>
    </a>
  </div>

Only `data-ex-menu-div="EXM01"` (standard exhibition) cards are processed —
`EOM01` outdoor-sculpture cards etc. are skipped, mirroring photo_sema.
NOTE (2026-07-20): the recon notes mentioned a `data-ex-enddt` attribute; the
live cards do NOT carry it, and we don't need it.

Detail URL: https://sema.seoul.go.kr/kr/whatson/exhibition/detail?exNo=<IDX>
Description lives in `div.o_body` (paragraphs_text, meta fallback).

Pagination: `&currentPage=N`. Past the last page the server still returns a
single EMPTY `div.viewLink` template (no `data-idx`), so the stop signal is
"no card with a data-idx", not "no div.viewLink at all".

Branch exclusion: cards whose venue text contains "사진미술관" are SKIPPED —
the dedicated `photo_sema` source already crawls the 서울시립 사진미술관 branch
(exPlace=ORG51) and yielding them here would create duplicate rows.

Media gate: SeMA is a general art museum (mostly painting/sculpture), so each
card passes the shared photo/film/media keyword gate
(:mod:`crawler.sources._media`): broad keywords over the curated short text
(title + venue name), strict compounds over the detail-page description.
Expect few yields per run — that is the filter working, not a parser fault.
Because the venue name is part of the short text, a branch whose NAME carries
a media keyword auto-passes every show there — today that is only
"백남준을 기억하는 집" (백남준 → 영상), which is a Nam June Paik memorial
venue where that recall-biased behaviour is intended.

Gotcha: do NOT hit `/kr/whatson/exhibition` or `/ex/currEx` (HTTP 500) — the
landing URL above is the only working list endpoint (see photo_sema recon).

Robots: no robots.txt restriction found; crawl respectfully (1 s delay).
"""

from __future__ import annotations

import re
import time
from collections.abc import Iterable

import httpx
from selectolax.parser import HTMLParser
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

from crawler.models import RawExhibition, SourceName
from crawler.sources._detail import MIN_DESCRIPTION_LEN, meta_description, paragraphs_text
from crawler.sources._media import media_category
from crawler.sources.base import register_source

_BASE = "https://sema.seoul.go.kr"
_LIST_URL = f"{_BASE}/kr/whatson/landing?whatsonMenuDivList=EX&whenType=FROM_TODAY"
_DETAIL_BASE = f"{_BASE}/kr/whatson/exhibition/detail"
_USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Safari/537.36"
)

# All SeMA branches sit in Seoul; the geocoder resolves the exact address
# from venue name + region, so no per-branch address table is needed.
_VENUE_REGION = "서울"

# Cards at this branch belong to the dedicated photo_sema source.
_PHOTO_SEMA_KEYWORD = "사진미술관"


class SemaExtractor:
    name = SourceName.SEMA
    country = "KR"

    def __init__(
        self,
        max_pages: int = 10,
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
        url = _LIST_URL
        if page > 1:
            url = f"{url}&currentPage={page}"
        r = self._client.get(url)
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
            # Stop on the raw card count, not the filtered one: a page holding
            # only EOM01 / 사진미술관 / non-media cards must not end pagination.
            if not _has_cards(html):
                return

            for c in _extract_cards(html):
                url = c["source_url"]
                if url in seen:
                    continue
                seen.add(url)
                payload = {k: v for k, v in c.items() if k != "source_url"}

                # The detail description feeds the strict tier of the media
                # gate, so it is fetched BEFORE filtering. A failed fetch
                # falls back to gating on the short text alone.
                if self.with_details:
                    try:
                        payload.update(_parse_detail(self._get_url(url)))
                    except Exception:  # noqa: BLE001 — partial data beats aborting
                        pass
                    if self.delay_s > 0:
                        time.sleep(self.delay_s)

                # Photo/film/media gate: broad keywords over title + venue,
                # strict compounds over the detail description.
                category = media_category(
                    f"{payload['title']} {payload.get('venue_name') or ''}",
                    payload.get("description"),
                )
                if category is None:
                    continue
                payload["category"] = category

                yield RawExhibition(
                    source=SourceName.SEMA,
                    source_url=url,
                    raw=payload,
                )

            if self.delay_s > 0:
                time.sleep(self.delay_s)


def _has_cards(html: str) -> bool:
    """True when the page holds at least one real card (a `data-idx` div).

    Past the last page the server still renders one empty `div.viewLink`
    template without `data-idx`, so mere `div.viewLink` presence is not a
    reliable pagination signal.
    """
    doc = HTMLParser(html)
    return any(div.attributes.get("data-idx") for div in doc.css("div.viewLink"))


def _extract_cards(html: str) -> list[dict]:
    """Parse a landing page into card dicts (pre-media-gate).

    Returns dicts with keys: source_url, title, venue_name, venue_region,
    date_range, poster_image_url, artists.

    Skips non-EXM01 sub-types and 사진미술관 cards (photo_sema's branch).
    """
    doc = HTMLParser(html)
    cards: list[dict] = []

    for div in doc.css("div.viewLink"):
        idx = div.attributes.get("data-idx")
        ex_menu_div = div.attributes.get("data-ex-menu-div", "")
        # Only standard exhibitions (not outdoor/biennale/festival sub-types)
        if not idx or ex_menu_div != "EXM01":
            continue

        source_url = f"{_DETAIL_BASE}?exNo={idx}"

        # Poster image (relative /common/imgFileView path → absolutize)
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

        # Venue — .epEcPlaceNm holds many blank child spans; text(strip=True)
        # merges them, leaving a trailing comma to strip.
        venue_el = div.css_first("span.epEcPlaceNm")
        venue_name: str | None = None
        if venue_el:
            venue_cleaned = re.sub(r",\s*$", "", venue_el.text(strip=True)).strip()
            if venue_cleaned:
                venue_name = venue_cleaned

        # Branch exclusion: 사진미술관 belongs to the photo_sema source.
        if venue_name and _PHOTO_SEMA_KEYWORD in venue_name:
            continue

        # Date range — native YYYY/MM/DD~YYYY/MM/DD parses fine downstream.
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
            "venue_region": _VENUE_REGION,
            "date_range": date_range,
            "poster_image_url": poster,
            "artists": [],
        })

    return cards


def _parse_detail(html: str) -> dict:
    """Pull the exhibition blurb from a SeMA detail page.

    The intro prose lives in `div.o_body` (the expandable 전시 안내 section) —
    identical markup to the photo_sema branch. Falls back to the meta
    description if that container moves.
    """
    doc = HTMLParser(html)
    body = doc.css_first("div.o_body")
    text = paragraphs_text(body) if body is not None else ""
    if len(text) < MIN_DESCRIPTION_LEN:
        text = meta_description(doc) or text
    return {"description": text} if len(text) >= MIN_DESCRIPTION_LEN else {}


# Register on import
register_source(SourceName.SEMA, SemaExtractor)
