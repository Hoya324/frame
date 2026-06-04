"""Art Space J / 아트스페이스 J (artspacej.com) — HTML extractor.

Strategy (recon 2026-06-04):
A photography-only space ("SPACE FOR PHOTO") in Seongnam, heavy on solo shows.
The site is self-built PHP; its HTTPS root WAF-returns 406 and the cert is
self-signed, so we use the **http** ``/sub/*.php`` board paths with a browser
UA. We crawl current (``sub03_01.php``) + upcoming (``sub03_03.php``).

List rows live in ``div.ExhibiList`` as a table where each ``<tr>`` carries a
thumbnail anchor (image only, empty text) and a title anchor, both pointing at
the same ``mode=view&idx=<n>`` detail href. The title anchor text is
``[CUBE1]작가 개인전_부제_2026.05.06-06.30`` (subtitles sometimes wrapped in
``<...>``), and the canonical date sits in a sibling ``<td>`` as
``2026.05.06<br>~<br>2026.06.30``, so we read the date from the whole row.

The hrefs are absolute ``/sub/...`` paths that also append a session-scoped
``PHPSESSID`` (and empty ``sk/sw/offset``) param; we canonicalize each URL down
to ``boardid``+``mode=view``+``idx`` so it stays stable across runs and dedupes
the twin anchors. A malformed upcoming-teaser anchor (``idx=--``) is dropped.

Detail pages expose no og:image, so the poster comes from the first
``/uploaded/board/exhib`` image in the body; the prose is the body's ``<p>``
text (nav/footer carry no paragraphs).
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

_BASE_URL = "http://www.artspacej.com"
_LIST_URLS = (
    f"{_BASE_URL}/sub/sub03_01.php?boardid=exhib",  # current
    f"{_BASE_URL}/sub/sub03_03.php?boardid=exhib",  # upcoming
)
_USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Safari/537.36"
)

_VENUE_NAME = "Art Space J"
_VENUE_REGION = "성남"
_VENUE_ADDRESS = "경기도 성남시 분당구 정자일로 166 SPG Dream Bldg. 1층"

_VIEW_HREF_RE = re.compile(r"mode=view")
_IDX_RE = re.compile(r"idx=(\d+)")
_ROOM_TAG_RE = re.compile(r"^\s*\[[^\]]+\]\s*")  # leading [CUBE1] etc.
_TRAILING_DATE_RE = re.compile(r"_?\s*\d{4}\s*\.\s*\d{1,2}\s*\.\s*\d{1,2}.*$")


def _clean_title(text: str) -> str:
    """Strip a leading ``[CUBE1]`` room tag and a trailing date token."""
    t = _ROOM_TAG_RE.sub("", text)
    t = _TRAILING_DATE_RE.sub("", t)
    return clean_whitespace(t).rstrip("_ ")


def _canonical_url(href: str) -> str | None:
    """Resolve a list href to a stable ``...?boardid&mode=view&idx`` URL.

    The site appends a session ``PHPSESSID`` (and empty ``sk/sw/offset``) param
    that would otherwise break dedupe across runs, so we keep only the stable
    keys. Returns ``None`` for a malformed teaser anchor with no numeric idx.
    """
    absolute = urllib.parse.urljoin(_BASE_URL, href)
    parts = urllib.parse.urlsplit(absolute)
    params = dict(urllib.parse.parse_qsl(parts.query))
    idx = params.get("idx")
    if not idx or not idx.isdigit():
        return None
    keep = [("boardid", params.get("boardid", "exhib")), ("mode", "view"), ("idx", idx)]
    query = urllib.parse.urlencode(keep)
    return urllib.parse.urlunsplit((parts.scheme, parts.netloc, parts.path, query, ""))


def _row_text(node) -> str:
    """Whole-row text, walking up to the enclosing ``<tr>`` (date sibling cell)."""
    cur = node
    for _ in range(5):
        if cur is None:
            break
        if (cur.tag or "").lower() == "tr":
            return clean_whitespace(cur.text())
        cur = cur.parent
    return clean_whitespace(node.text())


def _parse_list(html: str) -> list[dict]:
    doc = HTMLParser(html)
    items: list[dict] = []
    seen: set[str] = set()
    for a in doc.css("a"):
        href = a.attributes.get("href") or ""
        if not _VIEW_HREF_RE.search(href):
            continue
        url = _canonical_url(href)
        if url is None or url in seen:
            continue
        # Each row has a twin image-only anchor (empty text) plus the title
        # anchor; skip the image one so we read the title from its own text
        # (the row text is polluted by the leading row-number/date cells).
        text = clean_whitespace(a.text())
        if not text:
            continue
        title = _clean_title(text)
        if not title:
            continue
        seen.add(url)
        # The canonical date lives in a sibling <td>, so read the whole row.
        date_range = extract_date_range(_row_text(a)) or extract_date_range(text)
        items.append({"source_url": url, "title": title, "date_range": date_range})
    return items


def _parse_detail(html: str) -> dict:
    doc = HTMLParser(html)
    poster = None
    for img in doc.css("img"):
        src = img.attributes.get("src") or ""
        if "uploaded/board/exhib" in src:
            poster = urllib.parse.urljoin(_BASE_URL, src)
            break
    body = doc.css_first("body")
    description = (paragraphs_text(body) if body is not None else None) or meta_description(doc)
    return {"poster_image_url": poster, "description": description}


class ArtSpaceJExtractor:
    name = SourceName.ART_SPACE_J
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
            verify=False,  # noqa: S501 — http-only board; guards an https redirect
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
            try:
                items = _parse_list(self._get(list_url))
            except Exception:  # noqa: BLE001 — one board failing shouldn't abort
                items = []
            for item in items:
                if item["source_url"] in seen:
                    continue
                seen.add(item["source_url"])
                try:
                    detail = _parse_detail(self._get(item["source_url"]))
                except Exception:  # noqa: BLE001
                    detail = {"poster_image_url": None, "description": None}
                raw = {
                    "title": item["title"],
                    "category": "사진",
                    "date_range": item["date_range"],
                    "venue_name": _VENUE_NAME,
                    "venue_region": _VENUE_REGION,
                    "venue_address": _VENUE_ADDRESS,
                    "poster_image_url": detail["poster_image_url"],
                    "description": detail["description"],
                    "artists": [],
                }
                yield RawExhibition(
                    source=SourceName.ART_SPACE_J,
                    source_url=item["source_url"],
                    raw=raw,
                )
                if self.delay_s > 0:
                    time.sleep(self.delay_s)


register_source(SourceName.ART_SPACE_J, ArtSpaceJExtractor)
