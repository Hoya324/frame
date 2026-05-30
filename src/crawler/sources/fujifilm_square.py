"""フジフイルム スクエア (FUJIFILM SQUARE, fujifilmsquare.jp) — list+detail extractor.

Strategy (recon 2026-05-31):
The venue is a dedicated photography gallery in Roppongi, Tokyo, so every
exhibition is photo (no genre whitelist needed). The ``/exhibition/`` index
path is WAF-blocked (403), but the homepage embeds the full current/upcoming
lineup as anchors of the form ``/exhibition/<YYMMDD_NN>.html``. Each detail
page is plain SSR HTML.

Pipeline:
1. GET / (homepage) → collect unique exhibition codes from the anchors.
2. GET each /exhibition/<code>.html → parse the ``<table>`` overview
   (開催期間 / 開館時間 / 会場), the og:title, the main-visual image and the
   intro paragraph.

Date note: 開催期間 reads e.g. ``2026年5月29日（金）～6月4日（木）`` — the end
side omits the year, which ``parse_date_range`` can't infer. We strip the
weekday parens and inject the start year into a yearless end before storing,
so both ends resolve. Cross-year ranges (end already carries 年) pass through
untouched.
"""

from __future__ import annotations

import re
import time
from collections.abc import Iterable
from urllib.parse import urljoin

import httpx
from selectolax.parser import HTMLParser
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

from crawler.models import RawExhibition, SourceName
from crawler.normalize.text import clean_whitespace
from crawler.sources._detail import MIN_DESCRIPTION_LEN, meta_description
from crawler.sources.base import register_source

_BASE_URL = "https://fujifilmsquare.jp"
_LIST_URL = f"{_BASE_URL}/"
_USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Safari/537.36"
)

_VENUE_NAME = "フジフイルム スクエア"
_VENUE_REGION = "東京"
_VENUE_ADDRESS = "東京都港区赤坂9-7-3 東京ミッドタウン・ウエスト1F"

_CODE_RE = re.compile(r"/exhibition/(\d{6}_\d{2})\.html")
_OG_TITLE_SUFFIX_RE = re.compile(r"\s*[|｜].*$")
_WEEKDAY_PAREN_RE = re.compile(r"（[^）]*）")
_RANGE_SPLIT_RE = re.compile(r"\s*[〜～~]\s*")


def _canonical_url(code: str) -> str:
    return f"{_BASE_URL}/exhibition/{code}.html"


def _normalize_date_range(text: str) -> str:
    """Drop weekday parens and back-fill a yearless end with the start year."""
    cleaned = _WEEKDAY_PAREN_RE.sub("", text).strip()
    m = re.match(r"(\d{4})年", cleaned)
    if not m:
        return cleaned
    parts = _RANGE_SPLIT_RE.split(cleaned, maxsplit=1)
    if len(parts) == 2 and "年" not in parts[1]:
        cleaned = f"{parts[0].strip()}～{m.group(1)}年{parts[1].strip()}"
    return cleaned


class FujifilmSquareExtractor:
    name = SourceName.FUJIFILM_SQUARE
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
        codes = _extract_codes(self._get(_LIST_URL))
        for code in codes:
            url = _canonical_url(code)
            try:
                raw = _parse_detail(self._get(url), code)
            except Exception:  # noqa: BLE001 — a single bad/missing page must not abort the run
                raw = None
            if self.delay_s > 0:
                time.sleep(self.delay_s)
            if not raw:
                continue
            yield RawExhibition(source=SourceName.FUJIFILM_SQUARE, source_url=url, raw=raw)


def _extract_codes(html: str) -> list[str]:
    """Collect unique exhibition codes from the homepage anchors, in order."""
    doc = HTMLParser(html)
    seen: list[str] = []
    for a in doc.css("a[href]"):
        m = _CODE_RE.search(a.attributes.get("href") or "")
        if m and m.group(1) not in seen:
            seen.append(m.group(1))
    return seen


def _parse_detail(html: str, code: str) -> dict | None:
    """Parse a single exhibition detail page into a RawExhibition raw dict.

    Returns None when the page carries no usable title (e.g. an error page).
    """
    doc = HTMLParser(html)

    title = ""
    og = doc.css_first('meta[property="og:title"]')
    if og:
        title = _OG_TITLE_SUFFIX_RE.sub("", og.attributes.get("content") or "").strip()
    if not title:
        return None

    fields: dict[str, str] = {}
    for tr in doc.css("tr"):
        th = tr.css_first("th")
        td = tr.css_first("td")
        if th and td:
            fields[clean_whitespace(th.text())] = clean_whitespace(td.text())

    date_range = fields.get("開催期間")
    if date_range:
        date_range = _normalize_date_range(date_range)

    poster = None
    for img in doc.css("img"):
        src = img.attributes.get("src") or ""
        if "photo_event" in src and "_mv" in src:
            poster = urljoin(_BASE_URL, src)
            break
    if poster is None:
        poster = f"{_BASE_URL}/assets/img/photo_event_{code}_mv.jpg"

    description = None
    intro = doc.css_first("p.section-content")
    if intro:
        text = clean_whitespace(intro.text())
        if len(text) >= MIN_DESCRIPTION_LEN:
            description = text
    if description is None:
        description = meta_description(doc)

    return {
        "title": title,
        # The venue is single-purpose (photography), so seed the medium text.
        "category": "写真",
        "date_range": date_range,
        "open_hours": fields.get("開館時間"),
        "venue_name": _VENUE_NAME,
        "venue_region": _VENUE_REGION,
        "venue_address": _VENUE_ADDRESS,
        "poster_image_url": poster,
        "description": description,
        "artists": [],
    }


register_source(SourceName.FUJIFILM_SQUARE, FujifilmSquareExtractor)
