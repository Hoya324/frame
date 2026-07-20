"""일민미술관 (Ilmin Museum of Art, ilmin.org) — WordPress/Divi HTML extractor.

Strategy (recon 2026-07-20):
A general art museum on Sejong-daero, Jongno-gu, Seoul (in the historic
Dong-A Ilbo building). It shows painting/design/media across genres, so every
show must pass the shared photo/film keyword gate (``_media.media_category``).

The site is WordPress with the Divi theme. The authoritative "currently on"
list is the server-rendered page:

    GET https://ilmin.org/exhibitions/current/

Exhibition cards are Divi ``et_pb_code`` custom-HTML modules; each card links
to a detail page at ``https://ilmin.org/exhibition/{slug}/``. (A WP REST list
exists at ``/wp-json/wp/v2/exhibition`` but its items carry no date range, so
we prefer the current page + detail-page approach.)

Pipeline:
1. GET the current page, collect + dedupe ``a[href*="/exhibition/"]`` links.
2. GET each detail page for:
   * title — ``og:title`` with the trailing `` - 일민미술관`` site suffix
     stripped (fallback ``<h1>``),
   * date range — hand-typed text like ``2026.6.26.(Fri) ― 2026.8.21.(Fri)``
     inside the Divi header blocks. English weekday parens are stripped and
     the HORIZONTAL BAR (U+2015 ``―``) separator — which ``_detail``'s range
     regex does not cover — is pre-replaced with ``~`` before
     ``extract_date_range`` canonicalizes the span,
   * description — ``paragraphs_text`` over ``div#main-content`` (Divi wraps
     the prose in ``et_pb_text`` modules whose paragraphs are plain ``<p>``);
     fallback ``meta_description``,
   * poster — ``og:image``.
3. Gate with ``media_category(title, description)``; out-of-scope shows
   (painting, design, …) are skipped. The returned "사진"/"영상" token seeds
   ``raw["category"]``.

2026-07-20 snapshot: the single current show 《다시 그린 세계 2026: 순수와
혼종》 is Korean traditional painting and does NOT pass the media gate, so a
live crawl correctly yields 0 rows (pre-filter count 1). Ilmin regularly hosts
photo/media shows, so the source will produce rows in future cycles.

Per-item detail failures are swallowed (the card is skipped) so one bad page
never aborts the crawl.
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

_BASE_URL = "https://ilmin.org"
_LIST_URL = f"{_BASE_URL}/exhibitions/current/"
_USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Safari/537.36"
)

_VENUE_NAME = "일민미술관"
_VENUE_REGION = "서울"
_VENUE_ADDRESS = "서울특별시 종로구 세종대로 152"

# Detail pages live at https://ilmin.org/exhibition/{slug}/ (singular).
_DETAIL_HREF_RE = re.compile(r"^https?://ilmin\.org/exhibition/[^/]+/?$")

# English weekday parens — ``(Fri)``, ``(Thurs.)``, ``(saturday)`` — sit
# between a date and its separator and would break the range regex. The
# Korean/CJK equivalents ``(금)`` are already handled inside
# ``extract_date_range`` itself.
_EN_WEEKDAY_PAREN_RE = re.compile(
    r"[（(]\s*(?:mon|tue|wed|thu|fri|sat|sun)[a-z]*\.?\s*[）)]", re.IGNORECASE
)

# Ilmin hand-types the span with a HORIZONTAL BAR (U+2015): ``2026.6.26. ―
# 2026.8.21.``. That codepoint is NOT in ``_detail._DATE_RANGE_RE``'s
# separator class (verified 2026-07-20), so we normalize it to ``~`` first.
_HORIZONTAL_BAR = "―"

# ``og:title`` carries a `` - 일민미술관`` site-name suffix appended by the SEO
# plugin; strip it (tolerate -, – or | as the joiner).
_TITLE_SUFFIX_RE = re.compile(r"\s*[-–|]\s*일민미술관\s*$")


def _extract_date(text: str) -> str | None:
    """Canonicalize an Ilmin-style hand-typed span.

    Strips English weekday parens and swaps the U+2015 separator for ``~``
    before delegating to the shared ``extract_date_range``.
    """
    cleaned = _EN_WEEKDAY_PAREN_RE.sub(" ", text)
    cleaned = cleaned.replace(_HORIZONTAL_BAR, "~")
    return extract_date_range(cleaned)


def _extract_links(html: str) -> list[str]:
    """Collect exhibition detail links from the current-shows page, in order.

    Cards are Divi ``et_pb_code`` modules; both the poster image and the title
    link to the same detail URL, so we dedupe while preserving first-seen
    order.
    """
    doc = HTMLParser(html)
    links: list[str] = []
    seen: set[str] = set()
    for a in doc.css("a[href]"):
        href = (a.attributes.get("href") or "").strip()
        if not _DETAIL_HREF_RE.match(href):
            continue
        # Canonicalize with a trailing slash so both link variants dedupe.
        if not href.endswith("/"):
            href += "/"
        if href in seen:
            continue
        seen.add(href)
        links.append(href)
    return links


def _parse_detail(html: str) -> dict:
    """Parse an Ilmin detail page into a pre-filter raw dict.

    The media gate is applied by the caller (``crawl``) so that tests — and
    the live-yield accounting — can distinguish "parsed but filtered out"
    from "not parsed at all".
    """
    doc = HTMLParser(html)

    # Title: og:title minus the site-name suffix; <h1> as fallback.
    title = ""
    og_title = doc.css_first('meta[property="og:title"]')
    if og_title is not None:
        title = clean_whitespace(og_title.attributes.get("content") or "")
    if not title:
        h1 = doc.css_first("h1")
        title = clean_whitespace(h1.text()) if h1 is not None else ""
    title = _TITLE_SUFFIX_RE.sub("", title)

    # Poster: og:image (absolute wp-content upload URL).
    poster: str | None = None
    og_image = doc.css_first('meta[property="og:image"]')
    if og_image is not None:
        poster = (og_image.attributes.get("content") or "").strip() or None

    # Date + description both live under the Divi builder's #main-content.
    main = doc.css_first("div#main-content")

    # The header et_pb_code block carries the full-form span
    # (``2026.6.26.(Fri) ― 2026.8.21.(Fri)``); it precedes the shorter
    # in-prose repeats, and extract_date_range takes the first match.
    date_range = _extract_date(main.text()) if main is not None else None

    description = paragraphs_text(main) if main is not None else ""
    if len(description) < MIN_DESCRIPTION_LEN:
        description = meta_description(doc) or ""

    return {
        "title": title,
        "date_range": date_range,
        "venue_name": _VENUE_NAME,
        "venue_region": _VENUE_REGION,
        "venue_address": _VENUE_ADDRESS,
        "poster_image_url": poster,
        "description": description if len(description) >= MIN_DESCRIPTION_LEN else None,
        "artists": [],
    }


class IlminExtractor:
    name = SourceName.ILMIN
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
        links = _extract_links(self._get(_LIST_URL))
        for url in links:
            try:
                raw = _parse_detail(self._get(url))
            except Exception:  # noqa: BLE001 — one bad detail must not abort the run
                raw = None
            if self.delay_s > 0:
                time.sleep(self.delay_s)
            if not raw or not raw["title"]:
                continue
            # Photo/film gate: broad keywords on the title, strict compound
            # keywords on the long description (see _media docstring).
            category = media_category(raw["title"], raw.get("description"))
            if category is None:
                continue
            raw["category"] = category
            yield RawExhibition(
                source=SourceName.ILMIN,
                source_url=url,
                raw=raw,
            )


register_source(SourceName.ILMIN, IlminExtractor)
