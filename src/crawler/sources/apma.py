"""아모레퍼시픽미술관 (APMA, apma.amorepacific.com) — HTML extractor.

Strategy (recon 2026-07-20):
A corporate art museum in the Amorepacific HQ, Yongsan-gu, Seoul. It shows
collection highlights across all media, so every card must pass the shared
photo/film keyword gate (``_media.media_category``).

List (server-rendered, first page only):

    GET https://apma.amorepacific.com/contents/exhibition/index.do

Card structure: ``ul#photoLst_wrap > li.photoLst``. Only ``li`` with an
``<a href="/contents/exhibition/{id}/view.do">`` are exhibition cards — the
list interleaves decorative ``li.photoLst`` (``div.fixedBox`` badges/logos)
that we skip. Per card: thumbnail ``img.lazy[data-src]`` (already absolute on
``image-apma.amorepacific.com``), title ``span.tit`` (nested em/b/strong —
take the combined text). The list carries NO dates. Past shows live behind an
AJAX archive (``/contents/exhibition/ajax/index.do``) that is out of scope —
we crawl the first page only.

Detail: ``GET /contents/exhibition/{id}/view.do``
* title — ``h3.tit`` (fallback: the list-card title),
* period — ``li.place``: ``2026.04.01(수) – 2026.08.02(일) | 미술관 1F로비, …``;
  we take the part before ``|``. Korean weekday parens and the en-dash are
  both already handled by ``_detail.extract_date_range``,
* description — the prose is NOT server-rendered: it lives in an inline
  ``let content = {...};`` JSON blob whose ``description1`` key holds an HTML
  string. We regex the JSON string literal out, decode it, and run
  ``paragraphs_text`` over the parsed HTML (fallback ``meta_description``),
* organizer — ``p.s_txt`` (e.g. ``기획: 아모레퍼시픽미술관 (APMA)``); noted
  for reference, not emitted.

Sub-page note: the list mixes the headline show with per-section ``작품소개``
sub-pages that share one date range (all part of 《APMA, CHAPTER FIVE》).
Sub-pages like ``육명심, 예술가의 초상`` are effectively per-section shows and
are worth listing on their own, so we keep every card that passes the media
gate rather than deduping against a parent (there is no standalone parent
card in the 2026-07-20 snapshot).

Media gate: ``media_category(title, description)`` — e.g. ``한국 현대사진,
멈춤과 흐름`` passes via the title's broad ``사진``; ``육명심, 예술가의 초상``
passes via strict compounds (``사진가``) in the prose; painting/sculpture
sub-pages and the ``전시관람 예약`` reservation card are dropped.

Anti-bot note: the site sits behind Imperva Incapsula, but plain requests
with the desktop-Chrome User-Agent below pass (verified 2026-07-20).

Per-item detail failures fall back to a title-only gate (no date/description)
so one bad page never aborts the crawl.
"""

from __future__ import annotations

import json
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

_BASE_URL = "https://apma.amorepacific.com"
_LIST_URL = f"{_BASE_URL}/contents/exhibition/index.do"
_USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Safari/537.36"
)

_VENUE_NAME = "아모레퍼시픽미술관"
_VENUE_REGION = "서울"
_VENUE_ADDRESS = "서울특별시 용산구 한강대로 100"

# Exhibition detail hrefs: /contents/exhibition/{numeric id}/view.do
_DETAIL_HREF_RE = re.compile(r"^/contents/exhibition/\d+/view\.do$")

# The detail body is injected client-side from ``let content = {...};`` —
# ``description1`` is a JSON string literal holding the prose HTML. The
# ``(?:[^"\\]|\\.)*`` body tolerates every escaped quote/backslash inside.
_DESCRIPTION1_RE = re.compile(r'"description1"\s*:\s*"((?:[^"\\]|\\.)*)"')


def _extract_cards(html: str) -> list[dict]:
    """Parse the list page into card dicts (source_url/title/poster).

    Decorative ``li.photoLst`` without an anchor (fixedBox badges) and
    anchors that don't match the detail-href shape are skipped. Dedupes by
    detail URL, preserving first-seen order.
    """
    doc = HTMLParser(html)
    cards: list[dict] = []
    seen: set[str] = set()

    for li in doc.css("ul#photoLst_wrap li.photoLst"):
        a = li.css_first("a[href]")
        if a is None:
            continue
        href = (a.attributes.get("href") or "").strip()
        if not _DETAIL_HREF_RE.match(href):
            continue
        url = _BASE_URL + href
        if url in seen:
            continue
        seen.add(url)

        # Title: span.tit nests em > b > strong — combined text is fine.
        tit = li.css_first("span.tit")
        title = clean_whitespace(tit.text()) if tit is not None else ""
        if not title:
            continue

        # Thumbnail: lazy-loaded, real URL in data-src (already absolute).
        poster: str | None = None
        img = li.css_first("img.lazy")
        if img is not None:
            src = (img.attributes.get("data-src") or img.attributes.get("src") or "").strip()
            if src:
                poster = src if src.startswith("http") else _BASE_URL + src

        cards.append({"source_url": url, "title": title, "poster_image_url": poster})

    return cards


def _blob_description(html: str) -> str:
    """Decode the ``description1`` prose out of the inline content blob.

    Returns "" when the blob (or the key) is absent or malformed.
    """
    m = _DESCRIPTION1_RE.search(html)
    if not m:
        return ""
    try:
        # Re-wrap the raw literal in quotes and let json undo the escapes
        # (\", \\, \/, \uXXXX) in one shot.
        desc_html = json.loads(f'"{m.group(1)}"')
    except ValueError:
        return ""
    return paragraphs_text(HTMLParser(desc_html))


def _parse_detail(html: str) -> dict:
    """Parse an APMA detail page into title/date_range/description fields.

    The media gate is applied by the caller (``crawl``) so tests and yield
    accounting can distinguish "parsed but filtered out" from "not parsed".
    """
    doc = HTMLParser(html)

    title_el = doc.css_first("h3.tit")
    title = clean_whitespace(title_el.text()) if title_el is not None else ""

    # ``li.place``: "<period> | <rooms>" — only the period part holds dates.
    # Korean weekday parens + en-dash are handled inside extract_date_range.
    date_range: str | None = None
    place = doc.css_first("li.place")
    if place is not None:
        period = place.text(strip=True).split("|")[0]
        date_range = extract_date_range(period)

    description = _blob_description(html)
    if len(description) < MIN_DESCRIPTION_LEN:
        description = meta_description(doc) or ""

    out: dict = {"date_range": date_range}
    if title:
        out["title"] = title
    if len(description) >= MIN_DESCRIPTION_LEN:
        out["description"] = description
    return out


class ApmaExtractor:
    name = SourceName.APMA
    country = "KR"

    def __init__(self, delay_s: float = 1.0, timeout_s: float = 30.0) -> None:
        self.delay_s = delay_s
        self._client = httpx.Client(
            timeout=timeout_s,
            headers={
                "User-Agent": _USER_AGENT,
                "Accept-Language": "ko,en-US;q=0.8,en;q=0.7",
            },
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
        cards = _extract_cards(self._get(_LIST_URL))
        for card in cards:
            raw = {
                "title": card["title"],
                "date_range": None,
                "venue_name": _VENUE_NAME,
                "venue_region": _VENUE_REGION,
                "venue_address": _VENUE_ADDRESS,
                "poster_image_url": card["poster_image_url"],
                "description": None,
                "artists": [],
            }
            try:
                detail = _parse_detail(self._get(card["source_url"]))
                raw.update(detail)
            except Exception:  # noqa: BLE001 — one bad detail must not abort the run
                # Fall through with list-card fields only; the media gate
                # below then runs on the title alone.
                pass
            if self.delay_s > 0:
                time.sleep(self.delay_s)

            # Photo/film gate: broad keywords on the title, strict compound
            # keywords on the long description (see _media docstring).
            category = media_category(raw["title"], raw.get("description"))
            if category is None:
                continue
            raw["category"] = category
            yield RawExhibition(
                source=SourceName.APMA,
                source_url=card["source_url"],
                raw=raw,
            )


register_source(SourceName.APMA, ApmaExtractor)
