"""KOBA (한국국제방송영상기자재전) — single-edition extractor.

Strategy: fetch the server-rendered info page at conference.kobashow.com,
parse the h4 title and structured table (기간, 장소), extract organizer from
the introductory paragraph. Yields one RawExhibition per call (the current
KOBA edition).

NOTE ON ARCHITECTURE: The main kobashow.com site is a React SPA that returns
only a <div id="root"> shell on all routes — unusable for static scraping.
The conference subsite (conference.kobashow.com) is classic server-rendered
ASP.NET with full HTML content.

Info page structure (verified 2026-05-28 with 2025 edition data):
  <h4>KOBA 2025 (제 33회 국제 방송·미디어·음향·조명 전시회)</h4>
  <table>
    <tr>
      <th>기간</th><td>2025년 5월 20일(화) ~ 23일(금)</td>
      <th>개장시간</th><td>10:00 a.m. ~ 5:00 p.m.</td>
    </tr>
    <tr>
      <th>장소</th><td>COEX 전시장 A, C, D홀 및 컨퍼런스센터 (서울특별시 ...)</td>
      ...
    </tr>
  </table>
  <p>한국이앤엑스와 한국방송기술인연합회가 공동주최하는 KOBA ...</p>
"""

from __future__ import annotations

import re
from collections.abc import Iterable

import httpx
from selectolax.parser import HTMLParser
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

from crawler.models import RawExhibition, SourceName
from crawler.sources._detail import MIN_DESCRIPTION_LEN, meta_description, paragraphs_text
from crawler.sources.base import register_source

_INFO_URL = "https://conference.kobashow.com/kor/about/info.asp"
_USER_AGENT = "PhotoExhibitionCrawler/0.1 (+contact@example.com)"

# Strip parenthetical address from venue string, e.g. "COEX ... (서울특별시 ...)"
_VENUE_PAREN_RE = re.compile(r"\s*\([^)]+\)\s*$")

# Extract the first organizer name from the intro paragraph.
# Pattern: text before "와" / "이" connector that immediately follows an org name.
# e.g. "한국이앤엑스와 한국방송기술인연합회가 공동주최..."  → "한국이앤엑스"
_ORGANIZER_RE = re.compile(r"^(.+?)(?:와|이)\s+(?:한국|방송|미디어)")


class KobaExtractor:
    name = SourceName.KOBA

    def __init__(
        self,
        delay_s: float = 1.0,
        timeout_s: float = 20.0,
    ) -> None:
        self.delay_s = delay_s
        self._client = httpx.Client(
            timeout=timeout_s,
            headers={"User-Agent": _USER_AGENT},
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
        html = self._get(_INFO_URL)
        result = _parse_info_page(html)
        if result is not None:
            yield RawExhibition(
                source=SourceName.KOBA,
                source_url=_INFO_URL,
                raw=result,
            )


def _parse_info_page(html: str) -> dict | None:
    """Parse the KOBA exhibition info page and return a raw payload dict.

    Returns None if required fields (title and date) cannot be extracted.
    """
    doc = HTMLParser(html)

    # ── title ────────────────────────────────────────────────────────────────
    h4 = doc.css_first("#content h4")
    if h4 is None:
        h4 = doc.css_first("h4")
    title = h4.text(strip=True) if h4 else None
    if not title:
        return None

    # ── table: build th → td mapping ─────────────────────────────────────────
    # Each row has interleaved th/td pairs (2 key-value pairs per row).
    field_map: dict[str, str] = {}
    for row in doc.css("table tr"):
        ths = row.css("th")
        tds = row.css("td")
        for th, td in zip(ths, tds, strict=False):
            key = th.text(strip=True)
            val = td.text(strip=True)
            if key:
                field_map[key] = val

    date_range = field_map.get("기간")
    if not date_range:
        return None

    venue_raw = field_map.get("장소", "")
    # Strip trailing parenthetical address "(서울특별시 ...)"
    venue_name = _VENUE_PAREN_RE.sub("", venue_raw).strip() or None

    # ── organizer: from intro paragraph ──────────────────────────────────────
    organizer: str | None = None
    for p in doc.css("p"):
        text = p.text(strip=True)
        if "주최" in text or "와" in text:
            m = _ORGANIZER_RE.match(text)
            if m:
                organizer = m.group(1).strip()
                break

    # ── description: the intro paragraphs in #content ────────────────────────
    # KOBA has no per-edition detail page; the blurb lives in the same info
    # page's intro <p> block (the table cells are th/td, not <p>, so they
    # don't bleed in). Fall back to the meta description if the layout moves.
    content = doc.css_first("#content")
    description = paragraphs_text(content) if content is not None else ""
    if len(description) < MIN_DESCRIPTION_LEN:
        description = meta_description(doc) or description

    payload = {
        "title": title,
        "venue_name": venue_name,
        "date_range": date_range,
        "organizer": organizer,
        "exhibition_type_text": "박람회",
    }
    if len(description) >= MIN_DESCRIPTION_LEN:
        payload["description"] = description
    return payload


# Register on import
register_source(SourceName.KOBA, KobaExtractor)
