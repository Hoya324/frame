"""ZEN FOTO GALLERY (zen-foto.jp) — HTML extractor.

Strategy (recon 2026-05-31):
A Roppongi (Tokyo) gallery specialized in Asian photography, so every show is
photo. The ``/jp/exhibitions`` index is server-rendered; each exhibition is an
``<a href="/jp/exhibition/<slug>">`` whose anchor text is empty (image tile), so
we fetch every detail page for its title, poster and date.

We read the Japanese pages because they carry a clean ``会期：YYYY年M月D日 — D日``
label, whereas the English blurb spells the dates out in prose. The end may omit
its year/month, which we back-fill from the start. Slugs contain smart quotes
(U+201C/U+2019), so we percent-encode each URL before fetching and emitting it.
"""

from __future__ import annotations

import re
import time
import urllib.parse
from collections.abc import Iterable
from datetime import date

import httpx
from selectolax.parser import HTMLParser
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

from crawler.models import RawExhibition, SourceName
from crawler.normalize.text import clean_whitespace
from crawler.sources.base import register_source

_BASE_URL = "https://zen-foto.jp"
_LIST_URL = f"{_BASE_URL}/jp/exhibitions"
_USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Safari/537.36"
)

_VENUE_NAME = "ZEN FOTO GALLERY"
_VENUE_REGION = "東京"
_VENUE_ADDRESS = "東京都港区六本木6-6-9 ピラミデビル208号室"
_OPEN_HOURS = "火－土 12:00－19:00 / 日・月・祝休廊"

_HREF_RE = re.compile(r"/jp/exhibition/")
# The "会期：" label holds the canonical span; the end may drop year and/or month.
_JP_RANGE_RE = re.compile(
    r"(\d{4})\s*年\s*(\d{1,2})\s*月\s*(\d{1,2})\s*日"  # start Y年M月D日
    r"[^0-9年]*?"  # weekday parens / separator / spaces
    r"(?:(\d{4})\s*年\s*)?"  # optional end year
    r"(?:(\d{1,2})\s*月\s*)?"  # optional end month
    r"(\d{1,2})\s*日"  # end day
)


def _extract_jp_date_range(text: str) -> str | None:
    """Pull the ``会期`` span from a JP detail page and canonicalize it.

    Matches ``YYYY年M月D日 … [YYYY年][M月]D日`` and back-fills a yearless/monthless
    end from the start. Returns ``None`` when no span is present.
    """
    m = _JP_RANGE_RE.search(text)
    if not m:
        return None
    sy, sm, sd = int(m.group(1)), int(m.group(2)), int(m.group(3))
    ey = int(m.group(4)) if m.group(4) else sy
    em = int(m.group(5)) if m.group(5) else sm
    ed = int(m.group(6))
    try:
        date(sy, sm, sd)
        date(ey, em, ed)
    except ValueError:
        return None
    return f"{sy:04d}.{sm:02d}.{sd:02d}~{ey:04d}.{em:02d}.{ed:02d}"


def _absolute_url(href: str) -> str:
    """Return an ASCII, percent-encoded absolute URL for a list href."""
    path = href if href.startswith("/") else urllib.parse.urlparse(href).path
    return _BASE_URL + urllib.parse.quote(path)


def _parse_list(html: str) -> list[str]:
    """Return the deduped, percent-encoded exhibition detail URLs."""
    doc = HTMLParser(html)
    urls: list[str] = []
    seen: set[str] = set()
    for a in doc.css("a"):
        href = a.attributes.get("href") or ""
        if not _HREF_RE.search(href):
            continue
        url = _absolute_url(href)
        if url in seen:
            continue
        seen.add(url)
        urls.append(url)
    return urls


def _og(doc: HTMLParser, prop: str) -> str | None:
    node = doc.css_first(f'meta[property="{prop}"]')
    if node is None:
        return None
    return clean_whitespace(node.attributes.get("content") or "") or None


def _parse_detail(html: str) -> dict:
    """Pull title, date span, poster and blurb from a JP detail page."""
    doc = HTMLParser(html)
    og_title = _og(doc, "og:title") or ""
    # og:title is "<exhibition> | ZEN FOTO GALLERY - …"; keep the left part.
    title = clean_whitespace(og_title.split("|")[0])
    body_text = clean_whitespace(doc.body.text()) if doc.body else ""
    return {
        "title": title or None,
        "date_range": _extract_jp_date_range(body_text),
        "poster_image_url": _og(doc, "og:image"),
        "description": _og(doc, "og:description"),
    }


class ZenFotoExtractor:
    name = SourceName.ZEN_FOTO
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
        for url in _parse_list(self._get(_LIST_URL)):
            try:
                detail = _parse_detail(self._get(url))
            except Exception:  # noqa: BLE001 — one bad detail must not abort the run
                continue
            if not detail["title"]:
                continue
            raw = {
                "title": detail["title"],
                # Asian-photography gallery: seed the medium text.
                "category": "写真",
                "date_range": detail["date_range"],
                "venue_name": _VENUE_NAME,
                "venue_region": _VENUE_REGION,
                "venue_address": _VENUE_ADDRESS,
                "open_hours": _OPEN_HOURS,
                "poster_image_url": detail["poster_image_url"],
                "description": detail["description"],
                "artists": [],
            }
            yield RawExhibition(
                source=SourceName.ZEN_FOTO,
                source_url=url,
                raw=raw,
            )
            if self.delay_s > 0:
                time.sleep(self.delay_s)


register_source(SourceName.ZEN_FOTO, ZenFotoExtractor)
