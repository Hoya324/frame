"""갤러리 브레송 (Gallery Bresson, gallerybresson.com) — WordPress REST extractor.

Strategy (recon 2026-05-31):
A dedicated photography gallery in Jung-gu, Seoul, so every show is photo (no
genre whitelist needed). The site is WordPress with a working REST API exposed
via the ``index.php?rest_route=`` form (pretty-permalink ``/wp-json/`` 404s).
Exhibitions live in the CURRENT (cat 279) and UPCOMING (cat 248) categories.

Pipeline:
1. GET the REST posts endpoint for cats 279,248 with ``_embed=1`` (one request;
   23 < per_page=100, so no pagination).
2. For each post: title from ``title.rendered``; poster from the embedded
   featured media; the exhibition date range is buried in the body text in a
   handful of hand-typed formats, so we extract it with a tolerant regex.

Date note: the body carries ranges like ``2025.8.1~8.30``, ``2025.04.21.~05.06``,
``2024.11.20~29`` (end is day-only) and ``2025. 1. 16 (목) – 1. 25 (토)``
(spaces, weekday parens, en-dash). We back-fill a yearless / monthless end from
the start and emit a canonical ``YYYY.MM.DD~YYYY.MM.DD`` string that
``parse_date_range`` resolves cleanly. Posts whose dates live only on the poster
image (no body date) get ``date_range = None``.
"""

from __future__ import annotations

import time
from collections.abc import Iterable

import httpx
from selectolax.parser import HTMLParser
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

from crawler.models import RawExhibition, SourceName
from crawler.normalize.text import clean_whitespace
from crawler.sources._detail import extract_date_range as _extract_date_range
from crawler.sources.base import register_source

# The site serves only plain HTTP — its HTTPS port presents an invalid
# (self-signed) certificate, and every REST ``link`` it returns is http://.
_BASE_URL = "http://gallerybresson.com"
_LIST_URL = f"{_BASE_URL}/index.php"
_LIST_PARAMS = {
    "rest_route": "/wp/v2/posts",
    "categories": "279,248",  # CURRENT, UPCOMING
    "per_page": "100",
    "_embed": "1",
}
_USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Safari/537.36"
)

_VENUE_NAME = "갤러리 브레송"
_VENUE_REGION = "서울"
_VENUE_ADDRESS = "서울특별시 중구 퇴계로 163"

def _featured_image(post: dict) -> str | None:
    media = (post.get("_embedded") or {}).get("wp:featuredmedia") or []
    if media and isinstance(media[0], dict):
        url = media[0].get("source_url")
        if url:
            return str(url)
    return None


def _parse_post(post: dict) -> dict | None:
    """Parse a single REST post into a RawExhibition raw dict.

    Returns None when the post carries no usable title.
    """
    title = clean_whitespace(HTMLParser(post["title"]["rendered"]).text())
    if not title:
        return None

    text = clean_whitespace(HTMLParser(post["content"]["rendered"]).text())

    return {
        "title": title,
        # The venue is single-purpose (photography), so seed the medium text.
        "category": "사진",
        "date_range": _extract_date_range(text),
        "venue_name": _VENUE_NAME,
        "venue_region": _VENUE_REGION,
        "venue_address": _VENUE_ADDRESS,
        "poster_image_url": _featured_image(post),
        "description": text or None,
        "artists": [],
    }


class GalleryBressonExtractor:
    name = SourceName.GALLERY_BRESSON
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
    def _get_posts(self) -> list[dict]:
        r = self._client.get(_LIST_URL, params=_LIST_PARAMS)
        r.raise_for_status()
        return r.json()

    def crawl(self) -> Iterable[RawExhibition]:
        for post in self._get_posts():
            try:
                raw = _parse_post(post)
            except Exception:  # noqa: BLE001 — one bad post must not abort the run
                raw = None
            if not raw:
                continue
            yield RawExhibition(
                source=SourceName.GALLERY_BRESSON,
                source_url=post["link"],
                raw=raw,
            )
        if self.delay_s > 0:
            time.sleep(self.delay_s)


register_source(SourceName.GALLERY_BRESSON, GalleryBressonExtractor)
