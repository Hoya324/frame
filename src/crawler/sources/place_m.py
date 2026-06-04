"""Place M / プレイスM (placem.com) — HTML extractor.

Strategy (recon 2026-06-04):
An artist-run photography gallery + darkroom in Shinjuku, Tokyo — every show is
photography, so we seed the medium text and skip genre filtering. The static
``/schedule/schedule.php`` page is a table: each row carries a dotted date span
in ``<td class="ymd">`` (``2026.06.01 - 2026.06.07``) and one or two
``<td class="sch">`` cells, each an anchor to
``../schedule/<YYYY>/<main|mini>/<YYYYMMDD>/exhibition.php`` with text
``作家「タイトル」``. Plain-text rows (no anchor) are upcoming shows without a
page yet and are skipped.

Detail pages expose no og:image, so the poster comes from the first ``<img>``
inside ``div.photo`` (the site logo lives in ``#logo``). The body prose sits in
``div.title`` as ``<br />``-separated lines, so we read its text directly rather
than via ``<p>`` paragraphs.
"""

from __future__ import annotations

import re
import time
import urllib.parse
from collections.abc import Iterable

import httpx
from selectolax.parser import HTMLParser
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

from crawler.models import RawExhibition, SourceName
from crawler.normalize.text import clean_whitespace
from crawler.sources._detail import extract_date_range, meta_description
from crawler.sources.base import register_source

_BASE_URL = "https://www.placem.com"
_LIST_URL = f"{_BASE_URL}/schedule/schedule.php"
_USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Safari/537.36"
)

_VENUE_NAME = "Place M"
_VENUE_REGION = "東京"
_VENUE_ADDRESS = "東京都新宿区新宿1-2-11 第二都ビル3F"

_HREF_RE = re.compile(r"schedule/\d{4}/(?:main|mini)/\d{8}/exhibition\.php")
_TITLE_RE = re.compile(r"「(.+?)」")


def _absolute(href: str) -> str:
    return urllib.parse.urljoin(_LIST_URL, href)


def _split_artist_title(text: str) -> tuple[list[str], str]:
    """``作家「タイトル」`` -> (["作家"], "タイトル"). Falls back to whole text."""
    tm = _TITLE_RE.search(text)
    if not tm:
        return [], clean_whitespace(text)
    title = clean_whitespace(tm.group(1))
    artist = clean_whitespace(text[: tm.start()])
    return ([artist] if artist else []), (title or clean_whitespace(text))


def _row_text(node) -> str:
    """Whole-row text, walking up to the enclosing ``<tr>`` (date sibling cell)."""
    cur = node
    for _ in range(4):  # a -> td -> tr is two hops; a little slack for nesting.
        if cur is None:
            break
        if (cur.tag or "").lower() == "tr":
            return clean_whitespace(cur.text())
        cur = cur.parent
    return clean_whitespace(node.text())


def _parse_list(html: str) -> list[dict]:
    """Return one ``{source_url, title, artists, date_range}`` per exhibition."""
    doc = HTMLParser(html)
    items: list[dict] = []
    seen: set[str] = set()
    for a in doc.css("a"):
        href = a.attributes.get("href") or ""
        if not _HREF_RE.search(href):
            continue
        url = _absolute(href)
        if url in seen:
            continue
        seen.add(url)
        text = clean_whitespace(a.text())
        artists, title = _split_artist_title(text)
        if not title:
            continue
        # The date lives in a sibling cell, so read it from the whole row.
        date_range = extract_date_range(_row_text(a)) or extract_date_range(text)
        items.append(
            {
                "source_url": url,
                "title": title,
                "artists": artists,
                "date_range": date_range,
            }
        )
    return items


def _parse_detail(html: str) -> dict:
    """Poster from the first ``div.photo`` image (no og:image); body prose."""
    doc = HTMLParser(html)
    poster = None
    og = doc.css_first('meta[property="og:image"]')
    if og is not None:
        poster = clean_whitespace(og.attributes.get("content") or "") or None
    if poster is None:
        # The site logo lives in #logo; the exhibition poster(s) are in div.photo.
        img = doc.css_first("div.photo img")
        src = img.attributes.get("src") if img is not None else None
        if src:
            poster = urllib.parse.urljoin(_BASE_URL, src)

    description = None
    title_block = doc.css_first("div.title")
    if title_block is not None:
        description = clean_whitespace(title_block.text()) or None
    if not description:
        description = meta_description(doc)
    return {"poster_image_url": poster, "description": description}


class PlaceMExtractor:
    name = SourceName.PLACE_M
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
                "category": "写真",
                "date_range": item["date_range"],
                "venue_name": _VENUE_NAME,
                "venue_region": _VENUE_REGION,
                "venue_address": _VENUE_ADDRESS,
                "poster_image_url": detail["poster_image_url"],
                "description": detail["description"],
                "artists": item["artists"],
            }
            yield RawExhibition(
                source=SourceName.PLACE_M,
                source_url=item["source_url"],
                raw=raw,
            )
            if self.delay_s > 0:
                time.sleep(self.delay_s)


register_source(SourceName.PLACE_M, PlaceMExtractor)
