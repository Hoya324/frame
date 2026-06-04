"""Totem Pole Photo Gallery / TPPG (tppg.jp) — HTML extractor.

Strategy (recon 2026-06-04):
An artist-run photography gallery in Yotsuya, Shinjuku, Tokyo (100% photo). The
WordPress homepage server-renders the current + upcoming shows in two distinct
layouts that we reconcile by walking each slug anchor up to its enclosing block:

* The **current** show is a ``<article>`` whose ``<div class="entry-content">``
  carries structured ``<p class="tppg-name">`` (artist), ``<p class="tppg-title">``
  (title) and ``<p class="tppg-date">`` (``2026.5.26 (tue) – 6.7 (sun)``) blocks.
* **Upcoming** shows live in ``aside`` widgets as ``<li class="cat-post-item">``
  whose ``<p class="cpwp-excerpt-text">`` reads
  ``作家 / Artist 写真展「タイトル」2026.6.9 (tue) – 6.14 (sun)``.

We keep only slug anchors whose enclosing block carries a dotted date span,
which naturally excludes the nav/utility links (about/access/contact/…). Detail
pages expose no og:image, so the poster comes from the WordPress featured image
(``figure.post-thumbnail img``) and the description from ``div.entry-content``.
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
from crawler.sources._detail import extract_date_range, meta_description, paragraphs_text
from crawler.sources.base import register_source

_BASE_URL = "https://tppg.jp"
_LIST_URL = f"{_BASE_URL}/"
_USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Safari/537.36"
)

_VENUE_NAME = "Totem Pole Photo Gallery"
_VENUE_REGION = "東京"
_VENUE_ADDRESS = "東京都新宿区四谷四丁目22 第二富士川ビル1F"

_SLUG_RE = re.compile(r"^https?://tppg\.jp/([^/]+)/$")
# Flat-slug pages that are sections/utility, not exhibitions. Anchors whose
# enclosing block has no dotted date span are already dropped; this is a belt.
_STOP_SLUGS = {
    "about", "access", "contact", "current", "upcoming", "past", "archive",
    "news", "member", "rental", "workshop", "shop", "category", "tag", "wp",
    "en", "privacy-policy", "law",
}
_TITLE_RE = re.compile(r"[\"“”「『](.+?)[\"”」』]")
_HAS_DATE_RE = re.compile(r"\d{4}\s*\.\s*\d{1,2}\s*\.\s*\d{1,2}")
# Trailing medium label that sits between artist and the quoted title.
_MEDIUM_SUFFIX_RE = re.compile(r"(?:写真展|個展|展)\s*$")
# English weekday parens (``(tue)``) sit between a date and its separator, which
# the shared CJK/Korean-only weekday stripper in ``extract_date_range`` misses.
_EN_WEEKDAY_PAREN_RE = re.compile(
    r"[（(]\s*(?:mon|tue|wed|thu|fri|sat|sun)\s*[）)]", re.IGNORECASE
)


def _date_range(text: str) -> str | None:
    """Strip English weekday parens, then defer to the shared extractor."""
    return extract_date_range(_EN_WEEKDAY_PAREN_RE.sub(" ", text))


def _block_for(node):
    """Walk up to the enclosing exhibition block: ``<article>`` or ``li.cat-post-item``."""
    cur = node
    for _ in range(6):
        if cur is None:
            break
        tag = (cur.tag or "").lower()
        cls = cur.attributes.get("class") or ""
        if tag == "article" or (tag == "li" and "cat-post-item" in cls):
            return cur
        cur = cur.parent
    return node


def _split_artist_title(text: str) -> tuple[list[str], str]:
    """``作家 / Artist 写真展「タイトル」`` -> (["作家 / Artist"], "タイトル")."""
    tm = _TITLE_RE.search(text)
    if tm:
        title = clean_whitespace(tm.group(1))
        artist = clean_whitespace(_MEDIUM_SUFFIX_RE.sub("", text[: tm.start()]))
        return ([artist] if artist else []), (title or clean_whitespace(text))
    dm = _HAS_DATE_RE.search(text)
    title = clean_whitespace(text[: dm.start()]) if dm else clean_whitespace(text)
    return [], (title or clean_whitespace(text))


def _meta_from_block(block, anchor_title: str) -> dict | None:
    """Pull (title, artists, date_range) from a current-article or upcoming-li block."""
    # Current article: structured tppg-* paragraphs.
    name = block.css_first("p.tppg-name")
    title_p = block.css_first("p.tppg-title")
    date_p = block.css_first("p.tppg-date")
    if title_p is not None or date_p is not None:
        date_text = clean_whitespace(date_p.text()) if date_p is not None else ""
        date_range = _date_range(date_text)
        if not date_range:
            return None
        title = clean_whitespace(title_p.text()) if title_p is not None else anchor_title
        artists = []
        if name is not None:
            artist = clean_whitespace(name.text())
            if artist:
                artists = [artist]
        return {
            "title": title or anchor_title,
            "artists": artists,
            "date_range": date_range,
        }
    # Upcoming li: one excerpt line "作家 / Artist 写真展「タイトル」date".
    excerpt = block.css_first("p.cpwp-excerpt-text")
    node = excerpt if excerpt is not None else block
    source_text = clean_whitespace(node.text())
    date_range = _date_range(source_text)
    if not date_range:
        return None
    artists, title = _split_artist_title(source_text)
    # Prefer the anchor's own title (clean, no medium label) when available.
    title = anchor_title or title
    if not title:
        return None
    return {"title": title, "artists": artists, "date_range": date_range}


def _parse_list(html: str) -> list[dict]:
    """Return one ``{source_url, title, artists, date_range}`` per current/upcoming show."""
    doc = HTMLParser(html)
    items: list[dict] = []
    seen: set[str] = set()
    for a in doc.css("a"):
        href = a.attributes.get("href") or ""
        url = urllib.parse.urljoin(_BASE_URL + "/", href)
        m = _SLUG_RE.match(url)
        if not m or m.group(1).lower() in _STOP_SLUGS:
            continue
        if url in seen:
            continue
        block = _block_for(a)
        if not _HAS_DATE_RE.search(clean_whitespace(block.text())):
            continue
        anchor_title = clean_whitespace(a.attributes.get("title") or a.text())
        meta = _meta_from_block(block, anchor_title)
        if meta is None:
            continue
        seen.add(url)
        items.append({"source_url": url, **meta})
    return items


def _parse_detail(html: str) -> dict:
    """Poster from the WordPress featured image (no og:image); body prose."""
    doc = HTMLParser(html)
    poster = None
    og = doc.css_first('meta[property="og:image"]')
    if og is not None:
        poster = clean_whitespace(og.attributes.get("content") or "") or None
    if poster is None:
        img = doc.css_first("figure.post-thumbnail img") or doc.css_first(
            "div.entry-content img"
        )
        src = img.attributes.get("src") if img is not None else None
        if src:
            poster = urllib.parse.urljoin(_BASE_URL, src)

    description = None
    body = doc.css_first("div.entry-content")
    if body is not None:
        description = paragraphs_text(body) or None
    if not description:
        description = meta_description(doc)
    return {"poster_image_url": poster, "description": description}


class TotemPoleExtractor:
    name = SourceName.TOTEM_POLE
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
                source=SourceName.TOTEM_POLE,
                source_url=item["source_url"],
                raw=raw,
            )
            if self.delay_s > 0:
                time.sleep(self.delay_s)


register_source(SourceName.TOTEM_POLE, TotemPoleExtractor)
