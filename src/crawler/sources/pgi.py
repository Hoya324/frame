"""PGI / フォト・ギャラリー・インターナショナル (pgi.ac) — HTML extractor.

Strategy (recon 2026-05-31):
A dedicated photography gallery in Minato-ku, Tokyo, so every show is photo (no
genre whitelist needed). The ``/exhibitions`` index is server-rendered: each
exhibition is an ``<a href="/exhibitions/<id>">`` whose text carries the title
followed by a hand-typed date span (``2026.5.22(金) － 7.11(土)``). We split the
title from the date there, then fetch each detail page for the ``og:image``
poster and the body prose.

Date note: spans use a ``(曜日)`` weekday in parens and a full-width hyphen, both
handled by the shared :func:`crawler.sources._detail.extract_date_range`.
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
from crawler.sources._detail import extract_date_range
from crawler.sources.base import register_source

_BASE_URL = "https://www.pgi.ac"
_LIST_URL = f"{_BASE_URL}/exhibitions"
_USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Safari/537.36"
)

_VENUE_NAME = "PGI"
_VENUE_REGION = "東京"
_VENUE_ADDRESS = "東京都港区東麻布2-3-4 TKBビル3F"
_OPEN_HOURS = "月－土 11:00－18:00 / 日・祝休館"

_HREF_RE = re.compile(r"/exhibitions/(\d+)")
# A date token begins at a 4-digit year that is immediately followed by a dot
# (so an in-title year like "PARIS PHOTO 2025 " is not mistaken for the start).
_DATE_START_RE = re.compile(r"\d{4}\s*\.\s*\d{1,2}")


def _parse_list(html: str) -> list[dict]:
    """Return one ``{source_url, title, date_range}`` dict per exhibition link."""
    doc = HTMLParser(html)
    items: list[dict] = []
    seen: set[str] = set()
    for a in doc.css("a"):
        href = a.attributes.get("href") or ""
        m = _HREF_RE.search(href)
        if not m:
            continue
        url = href if href.startswith("http") else f"{_BASE_URL}/exhibitions/{m.group(1)}"
        if url in seen:
            continue
        seen.add(url)
        text = clean_whitespace(a.text())
        date_range = extract_date_range(text)
        dm = _DATE_START_RE.search(text)
        title = clean_whitespace(text[: dm.start()]) if dm else text
        if not title:
            continue
        items.append({"source_url": url, "title": title, "date_range": date_range})
    return items


def _parse_detail(html: str) -> dict:
    """Pull the og:image poster and the body prose from a detail page."""
    doc = HTMLParser(html)
    poster = None
    og = doc.css_first('meta[property="og:image"]')
    if og is not None:
        poster = clean_whitespace(og.attributes.get("content") or "") or None

    body = doc.css_first("div.right-side-inner")
    paras: list[str] = []
    if body is not None:
        for p in body.css("p"):
            t = clean_whitespace(p.text())
            # Drop photo-credit captions and the bare leading date row.
            if not t or t.startswith("©") or _DATE_START_RE.match(t):
                continue
            paras.append(t)
    description = "\n\n".join(paras) or None
    return {"poster_image_url": poster, "description": description}


class PgiExtractor:
    name = SourceName.PGI
    country = "JP"

    def __init__(self, delay_s: float = 1.0, timeout_s: float = 30.0) -> None:
        self.delay_s = delay_s
        self._client = httpx.Client(
            timeout=timeout_s,
            headers={
                "User-Agent": _USER_AGENT,
                "Accept-Language": "ja,en-US;q=0.8,en;q=0.7",
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
        for item in _parse_list(self._get(_LIST_URL)):
            try:
                detail = _parse_detail(self._get(item["source_url"]))
            except Exception:  # noqa: BLE001 — one bad detail must not abort the run
                detail = {"poster_image_url": None, "description": None}
            raw = {
                "title": item["title"],
                # Single-purpose photography gallery: seed the medium text.
                "category": "写真",
                "date_range": item["date_range"],
                "venue_name": _VENUE_NAME,
                "venue_region": _VENUE_REGION,
                "venue_address": _VENUE_ADDRESS,
                "open_hours": _OPEN_HOURS,
                "poster_image_url": detail["poster_image_url"],
                "description": detail["description"],
                "artists": [],
            }
            yield RawExhibition(
                source=SourceName.PGI,
                source_url=item["source_url"],
                raw=raw,
            )
            if self.delay_s > 0:
                time.sleep(self.delay_s)


register_source(SourceName.PGI, PgiExtractor)
