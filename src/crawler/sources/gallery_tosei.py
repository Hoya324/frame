"""Gallery Tosei / ギャラリー冬青 (tosei-sha.jp) — HTML extractor.

Strategy (recon 2026-06-04):
A photography-only gallery run by the publisher 冬青社 in Tokyo. The site is a
hand-maintained static site that is **http-only and Shift_JIS-encoded**, so we
decode the bytes from Shift_JIS in ``_get``. The current + next show live on
``.../EXHIBITIONS/j_exhibitions.html`` under ``Current Exhibition`` /
``Next Exhibition`` headers.

The real markup is hand-typed and broken in two ways that defeat an anchor-based
scan: the current show's detail link is written ``<href="...j_Kawai.html">``
(missing the ``a`` tag, so it is not an element), and the next show's only anchor
points at the wrong path (``jpg/ARTISTS/j_Sugino.html``). So we instead anchor on
the **content cell**: each show is a ``<td>`` whose text holds a
``YYYY年M月D日(曜) - M月D日(曜)`` span. From that cell we read the title from the
``<font size="4">`` line (``作家写真展``, never the ``Coming Soon`` placeholder),
the detail href via a regex over the cell's raw HTML (the malformed ``<href=``
is recovered this way; absent it we fall back to the list URL with a fragment),
and the poster from the nearest ``EXHIBITIONS`` ``<img>`` in the enclosing row.

Dates use the JP ``年月日`` form, so we keep a source-local parser (copied from
``zen_foto``); running the dotted ``extract_date_range`` on this body would
misread artist birth-years.
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
from crawler.sources._detail import paragraphs_text
from crawler.sources.base import register_source

_BASE_URL = "http://www.tosei-sha.jp"
_LIST_URL = f"{_BASE_URL}/TOSEI-NEW-HP/html/EXHIBITIONS/j_exhibitions.html"
_USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Safari/537.36"
)

_VENUE_NAME = "Gallery Tosei"
_VENUE_REGION = "東京"
_VENUE_ADDRESS = "東京都中野区中央5-18-20"

# The hand-typed detail link is sometimes ``<href="...">`` (no ``a`` tag), so the
# lenient HTML parser drops it — we recover it from the raw markup with a regex.
_DETAIL_HREF_RE = re.compile(r'["\'](\.{0,2}[^"\']*?EXHIBITIONS/j_[^/"\']+\.html)["\']')
# The placeholder title for an unannounced show; never use it as a real title.
_PLACEHOLDER_TITLE = "Coming Soon"
_JP_RANGE_RE = re.compile(
    r"(\d{4})\s*年\s*(\d{1,2})\s*月\s*(\d{1,2})\s*日"  # start Y年M月D日
    r"[^0-9年]*?"  # weekday parens / separator / spaces
    r"(?:(\d{4})\s*年\s*)?"  # optional end year
    r"(?:(\d{1,2})\s*月\s*)?"  # optional end month
    r"(\d{1,2})\s*日"  # end day
)


def _extract_jp_date_range(text: str) -> str | None:
    """Match ``YYYY年M月D日 - [YYYY年][M月]D日`` and canonicalize it.

    Back-fills a yearless/monthless end from the start. Returns ``None`` when no
    span is present.
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


def _cell_title(cell) -> str | None:
    """Title from the ``<font size="4">`` line (``作家写真展``), skipping the placeholder."""
    for font in cell.css('font[size="4"]'):
        text = clean_whitespace(font.text())
        if text and text != _PLACEHOLDER_TITLE:
            return text
    return None


def _detail_url_for(raw_html: str, title: str, order: int) -> str:
    """Find the show's detail href near its title in the *raw* HTML.

    The hand-typed detail link is sometimes ``<href="...">`` (no ``a`` tag), so
    the lenient HTML parser drops it — we recover it from the raw markup instead.
    We window the raw HTML from this title onward and take the first
    ``EXHIBITIONS/j_<Name>.html`` (ignoring the index ``j_exhibitions.html``).
    A freshly-announced show has no usable link, so we fall back to a distinct,
    valid list-page anchor that still gives the show a stable ``source_url``.
    """
    start = raw_html.find(title)
    window = raw_html[start:] if start != -1 else raw_html
    for m in _DETAIL_HREF_RE.finditer(window):
        href = m.group(1)
        if "j_exhibitions" in href:
            continue
        return urllib.parse.urljoin(_LIST_URL, href)
    return f"{_LIST_URL}#show{order}"


def _row_poster(cell) -> str | None:
    """Poster ``<img>`` from the enclosing ``<tr>`` (sibling of the content cell)."""
    row = cell
    for _ in range(4):
        if row is None:
            break
        if (row.tag or "").lower() == "tr":
            break
        row = row.parent
    scope = row if row is not None else cell
    for img in scope.css("img"):
        src = img.attributes.get("src") or ""
        if "EXHIBITIONS" in src and "Coming soon" not in src:
            return urllib.parse.urljoin(_LIST_URL, src)
    return None


def _parse_list(html: str) -> list[dict]:
    """Return one ``{source_url, title, date_range, poster_image_url}`` per show.

    Each show is a ``<td class="j12">`` content cell holding a ``作家写真展`` title
    (``<font size="4">``) and a ``年月日`` span. The poster ``<img>`` sits in the
    enclosing row and the detail href is recovered from the raw markup.
    """
    doc = HTMLParser(html)
    items: list[dict] = []
    order = 0
    for cell in doc.css("td.j12"):
        date_range = _extract_jp_date_range(clean_whitespace(cell.text()))
        if date_range is None:
            continue
        title = _cell_title(cell)
        if not title:
            continue
        order += 1
        items.append(
            {
                "source_url": _detail_url_for(html, title, order),
                "title": title,
                "date_range": date_range,
                "poster_image_url": _row_poster(cell),
            }
        )
    return items


def _parse_detail(html: str) -> dict:
    doc = HTMLParser(html)
    body = doc.css_first("body")
    description = paragraphs_text(body) if body is not None else None
    return {"description": description or None}


class GalleryToseiExtractor:
    name = SourceName.GALLERY_TOSEI
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
        # Site is Shift_JIS; decode explicitly (httpx may mis-detect).
        return r.content.decode("shift_jis", errors="replace")

    def crawl(self) -> Iterable[RawExhibition]:
        for item in _parse_list(self._get(_LIST_URL)):
            description = None
            try:
                description = _parse_detail(self._get(item["source_url"]))["description"]
            except Exception:  # noqa: BLE001 — detail may 404 for new shows
                description = None
            raw = {
                "title": item["title"],
                "category": "写真",
                "date_range": item["date_range"],
                "venue_name": _VENUE_NAME,
                "venue_region": _VENUE_REGION,
                "venue_address": _VENUE_ADDRESS,
                "poster_image_url": item["poster_image_url"],
                "description": description,
                "artists": [],
            }
            yield RawExhibition(
                source=SourceName.GALLERY_TOSEI,
                source_url=item["source_url"],
                raw=raw,
            )
            if self.delay_s > 0:
                time.sleep(self.delay_s)


register_source(SourceName.GALLERY_TOSEI, GalleryToseiExtractor)
