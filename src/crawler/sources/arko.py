"""ARKO Art Center (아르코미술관) — static-HTML extractor with media gate.

Strategy: GET the ARKO Art Center exhibition board list. The board renders ALL
exhibitions (current AND past) with their date ranges directly in the list HTML,
so we date-filter in code instead of relying on the site's own tab filters.

URL pattern (verified 2026-07-20):
  List:   GET https://www.arko.or.kr/artcenter/board/list/506?bid=266
  Detail: GET https://www.arko.or.kr/artcenter/board/view/506?bid=266&cid=<CID>

IMPORTANT — do NOT use `dateLocation=now`: the "현재전시" tab is legitimately
empty between shows, which would look like a crawl failure. The unfiltered list
returns everything with dates, and we keep only shows whose end date is today or
later, or whose start date is in the future (current + upcoming).

Card structure (one `<li>` per exhibition inside `ul.researchBoardList`):
  <li>
    <div class="thum">
      <a href="/artcenter/board/view/506?bid=266&page=&amp;cid=717239&amp;bid=266">
        <img src="/artcenter/cwsattach/image/39/....gif" alt="TITLE">
      </a>
    </div>
    <div class="textBox">
      <a href="..."><span class="subject">TITLE</span></a>
      <div class="detail">
        <dl class="col2">
          <dt>전시기간</dt><dd>2026-05-22 ~ 2026-07-19</dd>
          <dt>관람료</dt><dd>무료</dd>
        </dl>
        <dl class="col2">
          <dt>오프닝</dt><dd>...</dd>
          <dt>장소</dt><dd>아르코미술관 제1, 2전시실</dd>
        </dl>
        <dl class="col1"><dt>작가</dt><dd>오민, 카밀 노먼트</dd></dl>
        ...
      </div>
    </div>
  </li>

Quirks:
- The card href carries an empty `page=` param and duplicated/entity-encoded
  params (`&amp;cid=...&amp;bid=266`). We extract the numeric `cid` by regex and
  rebuild a canonical detail URL instead of trusting the raw href.
- No pagination markup was present at recon time (6 cards, one page). The board
  paging block exists but is empty; a single GET covers the whole list.

Detail page: prose paragraphs live in `div.displaySet` inside the 안내 tab
(`#tabCon01`). Falls back to the tab container, then the meta description.

Media gate: ARKO is a general contemporary-art venue (painting, installation,
architecture, …), so every show is passed through
:func:`crawler.sources._media.media_category` with the title as short text and
the detail prose as long text. Only photo/film/media shows are yielded — zero
yields between media shows is CORRECT behaviour, not a parser bug.

Venue constants: 아르코미술관 / 서울 / 서울특별시 종로구 동숭길 3.

Robots: /robots.txt disallows nothing relevant; crawl respectfully (1 s delay).
"""

from __future__ import annotations

import re
import time
from collections.abc import Iterable
from datetime import date

import httpx
from selectolax.parser import HTMLParser
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

from crawler.models import RawExhibition, SourceName
from crawler.normalize.text import clean_whitespace
from crawler.sources._detail import MIN_DESCRIPTION_LEN, meta_description, paragraphs_text
from crawler.sources._media import media_category
from crawler.sources.base import register_source

_BASE = "https://www.arko.or.kr"
_LIST_URL = "https://www.arko.or.kr/artcenter/board/list/506?bid=266"
_DETAIL_URL = "https://www.arko.or.kr/artcenter/board/view/506?bid=266&cid={cid}"
_USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"
    " (KHTML, like Gecko) Chrome/120.0 Safari/537.36"
)

_VENUE_NAME = "아르코미술관"
_VENUE_REGION = "서울"
_VENUE_ADDRESS = "서울특별시 종로구 동숭길 3"

# Board list dates are machine-friendly: "2026-05-22 ~ 2026-07-19".
_LIST_DATE_RE = re.compile(r"(\d{4})-(\d{2})-(\d{2})\s*~\s*(\d{4})-(\d{2})-(\d{2})")
_CID_RE = re.compile(r"[?&](?:amp;)?cid=(\d+)")


class ArkoExtractor:
    name = SourceName.ARKO

    def __init__(
        self,
        delay_s: float = 1.0,
        timeout_s: float = 20.0,
        with_details: bool = True,
        today: date | None = None,
    ) -> None:
        self.delay_s = delay_s
        self.with_details = with_details
        # Injectable clock so tests stay deterministic against a fixed fixture.
        self.today = today or date.today()
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
        cards = _extract_cards(self._get(_LIST_URL))
        for c in cards:
            if not _is_current_or_upcoming(c.get("date_range"), self.today):
                continue

            url = c["source_url"]
            payload = {k: v for k, v in c.items() if k != "source_url"}

            description: str | None = None
            if self.with_details:
                # Per-item detail failures must not abort the crawl.
                try:
                    detail = _parse_detail(self._get(url))
                    description = detail.get("description")
                    payload.update(detail)
                except Exception:  # noqa: BLE001
                    pass
                if self.delay_s > 0:
                    time.sleep(self.delay_s)

            # Media gate: ARKO shows mostly non-photo contemporary art. Only
            # yield when the title/description signals photo/film/media.
            category = media_category(payload["title"], description)
            if category is None:
                continue
            payload["category"] = category

            yield RawExhibition(source=SourceName.ARKO, source_url=url, raw=payload)


def _is_current_or_upcoming(date_range: str | None, today: date) -> bool:
    """Keep shows whose end date is >= today OR whose start is in the future.

    Unparseable/absent ranges are dropped: every real ARKO board card carries a
    machine-formatted range, so a missing one means a notice row, not a show.
    """
    if not date_range:
        return False
    m = _LIST_DATE_RE.search(date_range)
    if not m:
        return False
    try:
        start = date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
        end = date(int(m.group(4)), int(m.group(5)), int(m.group(6)))
    except ValueError:
        return False
    return end >= today or start > today


def _extract_cards(html: str) -> list[dict]:
    """Parse the board list into card dicts.

    Returns dicts with keys: source_url, title, date_range, venue_name,
    venue_region, venue_address, poster_image_url, artists, and optionally
    fee_text.
    """
    doc = HTMLParser(html)
    cards: list[dict] = []

    for li in doc.css("ul.researchBoardList > li"):
        title_el = li.css_first(".textBox span.subject")
        title = title_el.text(strip=True) if title_el else ""
        if not title:
            continue

        # Canonical detail URL from the numeric cid (raw href carries an empty
        # page= param and entity-encoded duplicate bid params).
        cid: str | None = None
        for a in li.css("a"):
            m = _CID_RE.search(a.attributes.get("href") or "")
            if m:
                cid = m.group(1)
                break
        if not cid:
            continue

        # Labeled dt/dd pairs inside the .detail block.
        fields: dict[str, str] = {}
        for dl in li.css(".textBox .detail dl"):
            dts = dl.css("dt")
            dds = dl.css("dd")
            for dt, dd in zip(dts, dds, strict=False):
                label = dt.text(strip=True)
                value = clean_whitespace(dd.text())
                if label and value:
                    fields[label] = value

        img = li.css_first(".thum img")
        poster: str | None = None
        if img:
            src = img.attributes.get("src") or ""
            if src:
                poster = src if src.startswith("http") else _BASE + src

        artists = [a.strip() for a in fields.get("작가", "").split(",") if a.strip()]

        card: dict = {
            "source_url": _DETAIL_URL.format(cid=cid),
            "title": title,
            "date_range": fields.get("전시기간"),
            "venue_name": _VENUE_NAME,
            "venue_region": _VENUE_REGION,
            "venue_address": _VENUE_ADDRESS,
            "poster_image_url": poster,
            "artists": artists,
        }
        if fields.get("관람료"):
            card["fee_text"] = fields["관람료"]
        # 장소 (hall/room within the venue) is parsed into `fields` but not
        # emitted: normalize has no per-hall field, and folding it into
        # venue_name would fragment the venue entity.
        cards.append(card)

    return cards


def _parse_detail(html: str) -> dict:
    """Pull the exhibition blurb from an ARKO detail page.

    The 안내 tab renders CMS prose inside `div.displaySet`; paragraphs carry the
    전시소개 text. Falls back to the whole tab container, then the meta tags.
    """
    doc = HTMLParser(html)
    text = ""
    for sel in ("div.displaySet", "div#tabCon01"):
        node = doc.css_first(sel)
        if node is not None:
            for junk in node.css("style,script"):
                junk.decompose()
            text = paragraphs_text(node)
            if len(text) >= MIN_DESCRIPTION_LEN:
                break
    if len(text) < MIN_DESCRIPTION_LEN:
        text = meta_description(doc) or text
    return {"description": text} if len(text) >= MIN_DESCRIPTION_LEN else {}


# Register on import
register_source(SourceName.ARKO, ArkoExtractor)
