"""Artmap (art-map.co.kr) — data-endpoint extractor with detail enrichment.

Strategy: walk paginated POST batches from /data/new_exhibition.php for the
list, then GET each detail page (view.php?idx=NNNN) to enrich price, hours,
address, and artist names.

NOTE ON ARCHITECTURE: The Artmap list page (new_list.php) is a JavaScript shell
that injects cards via AJAX. The real data comes from:
  POST https://art-map.co.kr/data/new_exhibition.php
with form params: start (offset, +4 each batch), wrap (batch number, +1),
type, area, cate, od, v_cnt, online.

Card structure (verified 2026-05-28):
  <a href='view.php?idx=NNNN'>
    <img src='https://art-map.co.kr/art-map/public/...'>
    <div class='new_exh_list'>
      <span id='ttl_N'>TITLE</span>
      <span>VENUE_NAME/REGION</span>
      <span>YYYY.MM.DD ~ YYYY.MM.DD</span>
      <span class='mck'>...</span>   ← hidden checkbox, skip
    </div>
  </a>

Detail page table structure (verified 2026-05-28):
  <table id="view_table">
    <tr><th>기간<span>|</span></th><td>2026-05-19 - 2026-10-25</td></tr>
    <tr><th>시간<span>|</span></th><td>화~목 10:00~20:00 ...</td></tr>
    <tr><th>장소<span>|</span></th><td><a>이름/지역</a></td></tr>
    <tr><th>주소<span>|</span></th><td>서울 중구 덕수궁길 61</td></tr>
    <tr><th>휴관<span>|</span></th><td>월요일</td></tr>
    <tr><th>관람료<span>|</span></th><td>· 성인: 10,000원\n· ...</td></tr>
    <tr><th>전화번호<span>|</span></th><td>02-...</td></tr>
    <tr><th>사이트<span>|</span></th><td><a href="...">홈페이지 바로가기</a></td></tr>
    <tr><th>작가<span>|</span></th>
        <td><div class="aut_wrap"><div class="aut_name">유영국</div></div></td>
    </tr>
  </table>

Artists appear in two shapes inside the 작가 cell:
  · `.aut_name` — present when the artist is in artmap's DB
  · `.aut_wrap_other` — bare text fallback for unregistered names
Multiple `.aut_wrap`/`.aut_name` blocks indicate a group show.
"""

from __future__ import annotations

import re
import time
from collections.abc import Iterable

import httpx
from selectolax.parser import HTMLParser
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

from crawler.models import RawExhibition, SourceName
from crawler.sources.base import register_source

_DATA_URL = "https://art-map.co.kr/data/new_exhibition.php"
_BASE = "https://art-map.co.kr"
_USER_AGENT = "PhotoExhibitionCrawler/0.1 (+contact@example.com)"
_DETAIL_RE = re.compile(r"view\.php\?idx=(\d+)")
_BATCH_SIZE = 4  # server always returns 4 cards per batch
_PRICE_RE = re.compile(r"(\d{1,3}(?:,\d{3})*)\s*원")
_TH_SEP_RE = re.compile(r"\s*\|\s*$")


class ArtmapExtractor:
    name = SourceName.ARTMAP

    def __init__(
        self,
        max_batches: int = 20,
        delay_s: float = 1.0,
        timeout_s: float = 20.0,
        with_details: bool = True,
    ) -> None:
        self.max_batches = max_batches
        self.delay_s = delay_s
        self.with_details = with_details
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
    def _post(self, start: int, wrap: int) -> str:
        r = self._client.post(
            _DATA_URL,
            data={
                "start": str(start),
                "wrap": str(wrap),
                "type": "ing",
                "area": "0",
                "cate": "",
                "od": "2",
                "v_cnt": "0",
                "online": "0",
            },
        )
        r.raise_for_status()
        return r.text

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
        for batch_num in range(1, self.max_batches + 1):
            start = (batch_num - 1) * _BATCH_SIZE
            html = self._post(start=start, wrap=batch_num)

            # Server returns the literal string "end" when exhausted
            if html.strip() == "end":
                return

            cards = _extract_cards(html)
            if not cards:
                return

            for c in cards:
                url = c["source_url"]
                if url in seen:
                    continue
                seen.add(url)
                payload = {k: v for k, v in c.items() if k != "source_url"}
                if self.with_details:
                    try:
                        detail_html = self._get(url)
                        payload.update(_parse_detail(detail_html))
                    except Exception:  # noqa: BLE001
                        # Partial data is better than dropping the row; the
                        # list-page fields stay intact.
                        pass
                    if self.delay_s > 0:
                        time.sleep(self.delay_s)
                yield RawExhibition(
                    source=SourceName.ARTMAP,
                    source_url=url,
                    raw=payload,
                )

            if self.delay_s > 0:
                time.sleep(self.delay_s)


def _extract_cards(html: str) -> list[dict]:
    """Parse a batch HTML fragment into card dicts.

    Returns dicts with keys: source_url, title, venue_name, venue_region,
    date_range, poster_image_url.
    """
    doc = HTMLParser(html)
    cards: list[dict] = []

    for a in doc.css("a"):
        href = a.attributes.get("href") or ""
        m = _DETAIL_RE.search(href)
        if not m:
            continue
        idx = m.group(1)
        source_url = f"{_BASE}/exhibition/view.php?idx={idx}"

        # Poster image
        img = a.css_first("img")
        poster: str | None = img.attributes.get("src") if img else None
        if poster and not poster.startswith("http"):
            poster = _BASE + ("" if poster.startswith("/") else "/") + poster

        # Text fields from .new_exh_list spans
        # span[0]: title (has id='ttl_N')
        # span[1]: venue/region combined
        # span[2]: date range
        # span[3]: map checkbox (.mck) — skip
        spans = a.css(".new_exh_list span")

        title = spans[0].text(strip=True) if spans else ""
        if not title:
            continue

        venue_combined = spans[1].text(strip=True) if len(spans) > 1 else ""
        date_range = spans[2].text(strip=True) if len(spans) > 2 else ""

        venue_name: str | None = None
        venue_region: str | None = None
        if venue_combined:
            name_part, _, region_part = venue_combined.partition("/")
            venue_name = name_part.strip() or None
            venue_region = region_part.strip() or None

        cards.append({
            "source_url": source_url,
            "title": title,
            "venue_name": venue_name,
            "venue_region": venue_region,
            "date_range": date_range or None,
            "poster_image_url": poster or None,
        })

    return cards


_DETAIL_FIELD_MAP = {
    "시간": "open_hours",
    "주소": "venue_address",
    "관람료": "price_text",
}


def _parse_detail(html: str) -> dict:
    """Parse the view_table on an Artmap detail page into a normalized dict.

    Returns a dict with any subset of: open_hours, venue_address, price_text,
    price_min, price_max, artists. Missing fields are simply omitted so callers
    can `.update()` without overwriting None.
    """
    doc = HTMLParser(html)
    table = doc.css_first("table#view_table")
    if table is None:
        return {}

    out: dict = {}
    for tr in table.css("tr"):
        th = tr.css_first("th")
        td = tr.css_first("td")
        if th is None or td is None:
            continue
        label = _TH_SEP_RE.sub("", th.text(strip=True)).strip()
        if label == "작가":
            artists = _extract_artists(td)
            if artists:
                out["artists"] = artists
            continue
        if label not in _DETAIL_FIELD_MAP:
            continue
        value = _clean_cell_text(td.text())
        if not value:
            continue
        out[_DETAIL_FIELD_MAP[label]] = value

    price_text = out.get("price_text")
    if price_text:
        pmin, pmax = _parse_price(price_text)
        if pmin is not None:
            out["price_min"] = pmin
        if pmax is not None:
            out["price_max"] = pmax
        # Only expose fee_text when the numeric parser found nothing —
        # otherwise the keyword check in map_fee_type would short-circuit
        # to FREE on partial-price lines that contain '무료'.
        if pmin is None and pmax is None:
            out["fee_text"] = price_text
    return out


def _clean_cell_text(text: str) -> str:
    """Collapse the heavy whitespace artmap leaves in <td> cells."""
    lines = [ln.strip() for ln in text.splitlines()]
    lines = [ln for ln in lines if ln]
    return "\n".join(lines)


def _extract_artists(td_node) -> list[str]:
    names: list[str] = []
    for n in td_node.css(".aut_name"):
        name = n.text(strip=True)
        if name and name not in names:
            names.append(name)
    if names:
        return names
    for n in td_node.css(".aut_wrap_other"):
        name = n.text(strip=True)
        if name and name not in names:
            names.append(name)
    return names


def _parse_price(text: str) -> tuple[int | None, int | None]:
    """Parse Korean price text into (price_min, price_max).

    Rules:
    - Lines containing '할인' are discounts — skip them.
    - Bare '무료' contributes 0.
    - Numeric patterns like '10,000원' contribute that integer.
    - Returns (None, None) if no signal at all.
    """
    if not text:
        return None, None
    amounts: list[int] = []
    saw_free = False
    for raw_line in text.splitlines():
        line = raw_line.strip().lstrip("·").strip()
        if not line:
            continue
        if "할인" in line:
            continue
        prices = [int(m.replace(",", "")) for m in _PRICE_RE.findall(line)]
        if prices:
            amounts.extend(prices)
            continue
        if "무료" in line or "free" in line.lower():
            saw_free = True
    if not amounts and not saw_free:
        return None, None
    if not amounts:
        return 0, 0
    pmin = 0 if saw_free else min(amounts)
    pmax = max(amounts)
    return pmin, pmax


# Register on import
register_source(SourceName.ARTMAP, ArtmapExtractor)
