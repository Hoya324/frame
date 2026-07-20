"""백남준아트센터 (Nam June Paik Art Center, njp.ggcf.kr) — static-HTML extractor.

Strategy (recon 2026-07-20): GET /exhibitions — a single server-rendered page
listing the CURRENT and upcoming shows as `<li>` cards (no pagination). The
yearly archive under `/exhibitions/more?year=` is deliberately NOT crawled;
this source only yields current/upcoming shows.

Card structure (verified 2026-07-20):
  <li>
    <a href="/exhibitions/244">
      <div class="thumb" style="background-image: url('/storage/upload/…');">
      </div>
    </a>
    <div class="meta-info">
      <a href="…?tag=전시" class="category">전시</a>
      <a href="/exhibitions/244" class="title">별, 괘卦</a>
      <div class="date">2026. 7. 16.—2027. 2. 14.</div>
    </a>
  </li>

The date uses dotted parts with an em-dash separator
("2026. 7. 16.—2027. 2. 14."); `_detail.extract_date_range` handles both and
emits the canonical ``YYYY.MM.DD~YYYY.MM.DD`` form.

Detail page (`/exhibitions/{id}`, same CMS as the other ggcf.kr venues):
  - prose in `div.content` (paragraphs_text, meta-description fallback);
  - a `<dl>` metadata block whose `참여작가` row lists artists
    (comma-separated; group names may carry a parenthesised member roster,
    so the split is paren-aware);
  - `og:image` is currently EMPTY on detail pages — when the CMS starts
    populating it, it replaces the list thumbnail as a better poster.

The venue is single-purpose — it is the Nam June Paik centre, all video/media
art — so ``category`` is seeded "영상" unconditionally (no _media gate).

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
from crawler.normalize.text import clean_whitespace
from crawler.sources._detail import (
    MIN_DESCRIPTION_LEN,
    extract_date_range,
    meta_description,
    paragraphs_text,
)
from crawler.sources.base import register_source

_BASE_URL = "https://njp.ggcf.kr"
_LIST_URL = f"{_BASE_URL}/exhibitions"
_USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Safari/537.36"
)

_VENUE_NAME = "백남준아트센터"
_VENUE_REGION = "경기"
_VENUE_ADDRESS = "경기도 용인시 기흥구 백남준로 10"

# `background-image: url('/storage/upload/…')` on the card's div.thumb.
_BG_IMAGE_RE = re.compile(r"background-image\s*:\s*url\(\s*['\"]?([^'\")]+)['\"]?\s*\)")

# Detail hrefs look like /exhibitions/244 (relative) — nothing deeper.
_DETAIL_HREF_RE = re.compile(r"^(?:https?://njp\.ggcf\.kr)?/exhibitions/\d+$")


def _split_artists(text: str) -> list[str]:
    """Split a 참여작가 roster on top-level commas.

    Group entries carry a parenthesised member list — e.g.
    "얄루, 알오에스(강류, 김시월)" — so commas inside parens must not split.
    """
    names: list[str] = []
    depth = 0
    buf: list[str] = []
    for ch in text:
        if ch in "(（":
            depth += 1
        elif ch in ")）":
            depth = max(0, depth - 1)
        if ch in ",、·" and depth == 0:
            names.append("".join(buf))
            buf = []
        else:
            buf.append(ch)
    names.append("".join(buf))
    # Anything longer than a name is a stray clause, not an artist.
    return [n for n in (clean_whitespace(n) for n in names) if n and len(n) <= 40]


class NjpArtCenterExtractor:
    name = SourceName.NJP_ART_CENTER
    country = "KR"

    def __init__(
        self,
        delay_s: float = 1.0,
        timeout_s: float = 20.0,
        with_details: bool = True,
    ) -> None:
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
    def _get_url(self, url: str) -> str:
        r = self._client.get(url)
        r.raise_for_status()
        return r.text

    def crawl(self) -> Iterable[RawExhibition]:
        seen: set[str] = set()
        for c in _extract_cards(self._get_url(_LIST_URL)):
            url = c["source_url"]
            if url in seen:
                continue
            seen.add(url)
            payload = {k: v for k, v in c.items() if k != "source_url"}
            if self.with_details:
                try:
                    payload.update(_parse_detail(self._get_url(url)))
                except Exception:  # noqa: BLE001 — partial data beats aborting
                    pass
                if self.delay_s > 0:
                    time.sleep(self.delay_s)
            yield RawExhibition(
                source=SourceName.NJP_ART_CENTER,
                source_url=url,
                raw=payload,
            )


def _extract_cards(html: str) -> list[dict]:
    """Parse the /exhibitions page into card dicts.

    Returns dicts with keys: source_url, title, category, date_range,
    venue_name, venue_region, venue_address, poster_image_url, artists.
    """
    doc = HTMLParser(html)
    cards: list[dict] = []

    for a in doc.css("a.title"):
        href = a.attributes.get("href") or ""
        if not _DETAIL_HREF_RE.match(href):
            continue
        title = a.text(strip=True)
        if not title:
            continue

        source_url = href if href.startswith("http") else _BASE_URL + href

        # The <li> card wraps both the thumb anchor and the meta-info block.
        li = a.parent
        while li is not None and li.tag != "li":
            li = li.parent

        # Date — "2026. 7. 16.—2027. 2. 14." → canonical YYYY.MM.DD~YYYY.MM.DD
        date_range: str | None = None
        if li is not None:
            date_el = li.css_first("div.date")
            if date_el:
                date_range = extract_date_range(date_el.text(strip=True))

        # Thumbnail — inline background-image on div.thumb
        poster: str | None = None
        if li is not None:
            thumb = li.css_first("div.thumb")
            if thumb:
                m = _BG_IMAGE_RE.search(thumb.attributes.get("style") or "")
                if m:
                    src = m.group(1)
                    poster = src if src.startswith("http") else _BASE_URL + src

        cards.append({
            "source_url": source_url,
            "title": title,
            # Single-purpose venue (video/media art) — no _media gate needed.
            "category": "영상",
            "date_range": date_range,
            "venue_name": _VENUE_NAME,
            "venue_region": _VENUE_REGION,
            "venue_address": _VENUE_ADDRESS,
            "poster_image_url": poster,
            "artists": [],
        })

    return cards


def _parse_detail(html: str) -> dict:
    """Pull description / artists / poster upgrades from a detail page.

    Prose sits in `div.content`; the `<dl>` metadata block carries a
    `참여작가` row. `og:image` is empty today but is preferred as the poster
    the day the CMS starts filling it in.
    """
    doc = HTMLParser(html)
    out: dict = {}

    body = doc.css_first("div.content")
    text = paragraphs_text(body) if body is not None else ""
    if len(text) < MIN_DESCRIPTION_LEN:
        text = meta_description(doc) or text
    if len(text) >= MIN_DESCRIPTION_LEN:
        out["description"] = text

    # dl metadata: <dt>참여작가</dt><dd>백남준, …</dd>
    for dl in doc.css("dl"):
        dts = dl.css("dt")
        dds = dl.css("dd")
        for dt, dd in zip(dts, dds, strict=False):
            if "참여작가" in dt.text(strip=True):
                artists = _split_artists(dd.text(strip=True))
                if artists:
                    out["artists"] = artists
                break

    og = doc.css_first('meta[property="og:image"]')
    if og:
        content = (og.attributes.get("content") or "").strip()
        if content:
            out["poster_image_url"] = (
                content if content.startswith("http") else _BASE_URL + content
            )

    return out


# Register on import
register_source(SourceName.NJP_ART_CENTER, NjpArtCenterExtractor)
