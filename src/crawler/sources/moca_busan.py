"""MOCA Busan (부산현대미술관) — static-HTML extractor with media gate.

Strategy: GET the 현재전시 (current) and 예정전시 (upcoming) board lists on the
Busan city portal and parse the server-rendered thumbnail cards. The museum
shows contemporary art across all media, so every card is passed through the
photo/film/media keyword gate; only matching shows are yielded — zero yields
while only permanent installations are up is CORRECT behaviour.

URL pattern (verified 2026-07-20):
  Current:  GET https://www.busan.go.kr/moca/exhibition01           (?curPage=N)
  Upcoming: GET https://www.busan.go.kr/moca/exhibition02           (?curPage=N)
  Detail:   GET https://www.busan.go.kr/moca/exhibition0X/<nttNo>
            (same board segment as the list the card came from)

Card structure (one `<li>` per show inside `ul.thumbListType1`):
  <li>
    <a href="/moca/exhibition01/1619062">
      <span class="thumb"><img src="/comm/getImage?...&thumbTy=M" alt="...썸네일"></span>
      <span class="titBar">
        <strong class="tit">Re: 새-새-의자</strong>
        <span class="exhibi_datetitle">-기간:
          <span class="date">2024. 3. 15.(금) ~ 상설</span></span>
      </span>
    </a>
  </li>

Date quirks:
- Permanent shows end with "상설" ("2018. 6. 16.(토) ~ 상설") and some upcoming
  shows carry a year-only range ("2026. ~ 2027."). Neither parses as a full
  span, so `_detail.extract_date_range` is applied to the raw text and
  `date_range` is set ONLY when a canonical span comes back — otherwise None
  (permanent/vague ranges are still yielded, just without dates).

Pagination: `?curPage=N`. The page reports "총 N건 (1/1page)"; out-of-range
pages re-serve page 1, so the crawler stops as soon as a page adds no new card
URLs (or none at all).

Detail page (`div.boardView`):
- Labeled `dl.form-data-info` rows: 전시시작일/전시종료일 (joined to recover a
  date range when the list text was truncated), 전시장소, 참여작가 (artists —
  headcount blurbs like "국외 작가 총 2명(팀)" are filtered out), 출품작, ….
- Prose in `dl.form-data-content div.se-contents` (SmartEditor markup with real
  `<p>` paragraphs) → `_detail.paragraphs_text`.

Media gate: `media_category(title, detail prose)`. At recon time the two
current shows are non-media permanent installations (correctly skipped) while
upcoming "소장품섬_뉴미디어와 미디어" passes on its title.

Venue constants: 부산현대미술관 / 부산 / 부산광역시 사하구 낙동남로 1191.

Robots: busan.go.kr robots.txt allows /moca; crawl respectfully (1 s delay).
"""

from __future__ import annotations

import re
import time
from collections.abc import Iterable

import httpx
from selectolax.parser import HTMLParser
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

from crawler.models import RawExhibition, SourceName
from crawler.normalize.text import clean_whitespace
from crawler.sources._detail import (
    MIN_DESCRIPTION_LEN,
    extract_date_range,
    meta_description,
    paragraphs_text,
)
from crawler.sources._media import media_category
from crawler.sources.base import register_source

_BASE = "https://www.busan.go.kr"
_LIST_URLS = (
    "https://www.busan.go.kr/moca/exhibition01",  # 현재전시
    "https://www.busan.go.kr/moca/exhibition02",  # 예정전시
)
_USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"
    " (KHTML, like Gecko) Chrome/120.0 Safari/537.36"
)

_VENUE_NAME = "부산현대미술관"
_VENUE_REGION = "부산"
_VENUE_ADDRESS = "부산광역시 사하구 낙동남로 1191"

_DETAIL_HREF_RE = re.compile(r"^/moca/exhibition0\d/\d+$")
# Artist dd cells that are headcount blurbs, not names ("국외 작가 총 2명(팀)").
# 미정 ("TBD") is handled as a whole-cell match below — it is also a common
# given name (김미정), so a substring match would drop real people.
_ARTIST_JUNK_RE = re.compile(r"총\s|\d+\s*명|\d+\s*팀")


class MocaBusanExtractor:
    name = SourceName.MOCA_BUSAN

    def __init__(
        self,
        max_pages: int = 5,
        delay_s: float = 1.0,
        timeout_s: float = 30.0,
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
    def _get(self, url: str) -> str:
        r = self._client.get(url)
        r.raise_for_status()
        return r.text

    def crawl(self) -> Iterable[RawExhibition]:
        seen: set[str] = set()
        for list_url in _LIST_URLS:
            for page in range(1, self.max_pages + 1):
                url = list_url if page == 1 else f"{list_url}?curPage={page}"
                cards = _extract_cards(self._get(url))
                # Out-of-range pages re-serve page 1: stop when nothing new.
                fresh = [c for c in cards if c["source_url"] not in seen]
                if not fresh:
                    break

                for c in fresh:
                    detail_url = c["source_url"]
                    seen.add(detail_url)
                    payload = {k: v for k, v in c.items() if k != "source_url"}

                    description: str | None = None
                    if self.with_details:
                        # Per-item detail failures must not abort the crawl.
                        try:
                            detail = _parse_detail(self._get(detail_url))
                            description = detail.get("description")
                            for k, v in detail.items():
                                if payload.get(k) in (None, "", []):
                                    payload[k] = v
                                elif k == "description":
                                    payload[k] = v
                        except Exception:  # noqa: BLE001
                            pass
                        if self.delay_s > 0:
                            time.sleep(self.delay_s)

                    # Media gate: keep photo/film/media shows only.
                    category = media_category(payload["title"], description)
                    if category is None:
                        continue
                    payload["category"] = category

                    yield RawExhibition(
                        source=SourceName.MOCA_BUSAN,
                        source_url=detail_url,
                        raw=payload,
                    )

                if self.delay_s > 0:
                    time.sleep(self.delay_s)


def _extract_cards(html: str) -> list[dict]:
    """Parse one board list page into card dicts.

    Returns dicts with keys: source_url, title, date_range (canonical or None),
    venue_name, venue_region, venue_address, poster_image_url, artists.
    """
    doc = HTMLParser(html)
    cards: list[dict] = []

    for a in doc.css("ul.thumbListType1 > li > a"):
        href = a.attributes.get("href") or ""
        if not _DETAIL_HREF_RE.match(href):
            continue

        tit = a.css_first("strong.tit")
        title = tit.text(strip=True) if tit else ""
        if not title:
            continue

        # "2018. 6. 16.(토) ~ 상설" / "2026. ~ 2027." → canonical span or None.
        date_range: str | None = None
        date_el = a.css_first("span.exhibi_datetitle span.date")
        if date_el:
            date_range = extract_date_range(date_el.text(strip=True))

        img = a.css_first("span.thumb img")
        poster: str | None = None
        if img:
            src = img.attributes.get("src") or ""
            if src:
                poster = src if src.startswith("http") else _BASE + src

        cards.append({
            "source_url": _BASE + href,
            "title": title,
            "date_range": date_range,
            "venue_name": _VENUE_NAME,
            "venue_region": _VENUE_REGION,
            "venue_address": _VENUE_ADDRESS,
            "poster_image_url": poster,
            "artists": [],
        })

    return cards


def _parse_detail(html: str) -> dict:
    """Pull description, artists, and a date fallback from a detail page."""
    doc = HTMLParser(html)
    out: dict = {}

    # Prose — SmartEditor content with real <p> paragraphs.
    text = ""
    node = doc.css_first("dl.form-data-content div.se-contents")
    if node is not None:
        for junk in node.css("style,script"):
            junk.decompose()
        text = paragraphs_text(node)
    if len(text) < MIN_DESCRIPTION_LEN:
        text = meta_description(doc) or text
    if len(text) >= MIN_DESCRIPTION_LEN:
        out["description"] = text

    # Labeled dt/dd rows (전시시작일 / 전시종료일 / 참여작가 / …).
    fields: dict[str, str] = {}
    for dl in doc.css("div.boardView dl.form-data-info"):
        dts = dl.css("dt")
        dds = dl.css("dd")
        for dt, dd in zip(dts, dds, strict=False):
            label = dt.text(strip=True)
            value = clean_whitespace(dd.text())
            if label and value:
                fields[label] = value

    start = fields.get("전시시작일")
    end = fields.get("전시종료일")
    if start and end:
        canonical = extract_date_range(f"{start} ~ {end}")
        if canonical:
            out["date_range"] = canonical

    if fields.get("참여작가"):
        artists = [
            name.strip()
            for name in fields["참여작가"].split(",")
            if name.strip()
            and name.strip() != "미정"
            and not _ARTIST_JUNK_RE.search(name)
        ]
        if artists:
            out["artists"] = artists

    return out


# Register on import
register_source(SourceName.MOCA_BUSAN, MocaBusanExtractor)
