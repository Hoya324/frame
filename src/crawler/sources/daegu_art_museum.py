"""Daegu Art Museum (대구미술관) — static-HTML extractor with media gate.

Strategy: GET the 현재전시 (current exhibitions) list on the museum CMS and
parse the server-rendered item cards. The museum's lineup is painting-heavy, so
every card is passed through the photo/film/media keyword gate; zero yields
during an all-painting season is CORRECT behaviour, not a parser bug.

DOMAIN NOTE: the museum moved to https://daeguartmuseum.or.kr — the old
artmuseum.daegu.go.kr host is DEAD (do not "fix" URLs back to it).

URL pattern (verified 2026-07-20):
  List:   GET https://daeguartmuseum.or.kr/index.do?menu_id=00000729
  Detail: GET https://daeguartmuseum.or.kr/index.do
              ?menu_id=00000729&menu_link=/front/ehi/ehiViewFront.do&ehi_id=<EHI_ID>

Card structure (one `div.item` per row inside `div.c_exh_lst`):
  <div class="item">
    <a href="javascript:fnView('EHI_00000335');">
      <span class="img"><span class="inr"><img src="/icms/file/getImage.do?..."></span></span>
      <span class="step ing">진행중</span>
      <span class="item_tit">2026 다티스트 《심윤： 회색 극장》</span>
      <span class="info_area">
        <span class="info"><em class="info_tit">기간</em>
          <span class="info_date">2026-07-14~2026-10-11</span></span>
        <span class="info"><em class="info_tit">장소</em><span>대구미술관 2, 3전시실</span></span>
      </span>
    </a>
    ...오디오 가이드 팝업 markup (same item_tit text repeated — scoped out)...
  </div>

Quirks:
- Card links are `javascript:fnView('EHI_########')` — the id is regexed out and
  a canonical GET detail URL is built (the site's own fnView() does a form POST,
  but plain GET with `ehi_id` in the query serves the same page).
- The list mixes in notice rows like "2026 전시일정" (a schedule announcement
  with a legitimate-looking date range). Guard: skip titles containing
  "전시일정", and require a parseable "YYYY-MM-DD~YYYY-MM-DD" date range.
- The list shows 8 items per page by default (`pageUnitF=8`); further pages are
  POST-driven. At recon time all 6 current shows fit on one page, so a single
  GET covers the list.

Detail page: prose lives in `div.exh_view_intro div.intro` (HWP-editor content,
`<br>`-separated inside spans — falls through `paragraphs_text` to whole-node
text). style/script nodes are decomposed defensively first.

Media gate: `media_category(title, detail prose)`. Current lineup (회화 위주)
yields nothing — verify the pre-filter card count when smoke-testing.

Venue constants: 대구미술관 / 대구 / 대구광역시 수성구 미술관로 40.

Robots: no restriction on /index.do; crawl respectfully (1 s delay).
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
from crawler.sources._detail import MIN_DESCRIPTION_LEN, meta_description, paragraphs_text
from crawler.sources._media import media_category
from crawler.sources.base import register_source

_BASE = "https://daeguartmuseum.or.kr"
_LIST_URL = "https://daeguartmuseum.or.kr/index.do?menu_id=00000729"
_DETAIL_URL = (
    "https://daeguartmuseum.or.kr/index.do"
    "?menu_id=00000729&menu_link=/front/ehi/ehiViewFront.do&ehi_id={ehi_id}"
)
_USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"
    " (KHTML, like Gecko) Chrome/120.0 Safari/537.36"
)

_VENUE_NAME = "대구미술관"
_VENUE_REGION = "대구"
_VENUE_ADDRESS = "대구광역시 수성구 미술관로 40"

_EHI_RE = re.compile(r"fnView\('(EHI_\d+)'\)")
_LIST_DATE_RE = re.compile(r"\d{4}-\d{2}-\d{2}\s*~\s*\d{4}-\d{2}-\d{2}")


class DaeguArtMuseumExtractor:
    name = SourceName.DAEGU_ART_MUSEUM

    def __init__(
        self,
        delay_s: float = 1.0,
        timeout_s: float = 30.0,
        with_details: bool = True,
    ) -> None:
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
    def _get(self, url: str) -> str:
        r = self._client.get(url)
        r.raise_for_status()
        return r.text

    def crawl(self) -> Iterable[RawExhibition]:
        cards = _extract_cards(self._get(_LIST_URL))
        seen: set[str] = set()
        for c in cards:
            url = c["source_url"]
            if url in seen:
                continue
            seen.add(url)
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

            # Media gate: painting-heavy museum — keep photo/film/media only.
            category = media_category(payload["title"], description)
            if category is None:
                continue
            payload["category"] = category

            yield RawExhibition(
                source=SourceName.DAEGU_ART_MUSEUM,
                source_url=url,
                raw=payload,
            )


def _extract_cards(html: str) -> list[dict]:
    """Parse the current-exhibition list into card dicts.

    Returns dicts with keys: source_url, title, date_range, venue_name,
    venue_region, venue_address, poster_image_url, artists. Notice rows
    ("전시일정") and rows without a parseable "YYYY-MM-DD~YYYY-MM-DD" range
    are skipped.
    """
    doc = HTMLParser(html)
    cards: list[dict] = []

    for item in doc.css("div.c_exh_lst div.item"):
        a = item.css_first("a")
        if a is None:
            continue
        m = _EHI_RE.search(a.attributes.get("href") or "")
        if not m:
            continue
        ehi_id = m.group(1)

        # Scope to the anchor: the audio-guide popup repeats the title below.
        tit = a.css_first(".item_tit")
        title = clean_whitespace(tit.text()) if tit else ""
        if not title or "전시일정" in title:
            continue  # schedule notice, not an exhibition

        date_el = a.css_first("span.info_date")
        date_range: str | None = None
        if date_el:
            dm = _LIST_DATE_RE.search(date_el.text())
            if dm:
                date_range = clean_whitespace(dm.group(0))
        if not date_range:
            continue  # every real show carries a machine-formatted range

        # 장소 (hall/room) is visible on the card but intentionally not
        # extracted: normalize has no per-hall field, and folding it into
        # venue_name would fragment the venue entity.
        img = a.css_first("span.img img")
        poster: str | None = None
        if img:
            src = img.attributes.get("src") or ""
            if src:
                poster = src if src.startswith("http") else _BASE + src

        cards.append({
            "source_url": _DETAIL_URL.format(ehi_id=ehi_id),
            "title": title,
            "date_range": date_range,
            "venue_name": _VENUE_NAME,
            "venue_region": _VENUE_REGION,
            "venue_address": _VENUE_ADDRESS,
            "poster_image_url": poster,
            "artists": [],
        })

    return cards


def _parse_detail(html: str) -> dict:
    """Pull the exhibition blurb from a Daegu Art Museum detail page.

    The 상세정보 tab renders HWP-editor prose in `div.exh_view_intro div.intro`.
    Falls back to the meta description if that container moves.
    """
    doc = HTMLParser(html)
    text = ""
    node = doc.css_first("div.exh_view_intro div.intro")
    if node is not None:
        for junk in node.css("style,script"):
            junk.decompose()
        text = paragraphs_text(node)
    if len(text) < MIN_DESCRIPTION_LEN:
        text = meta_description(doc) or text
    return {"description": text} if len(text) >= MIN_DESCRIPTION_LEN else {}


# Register on import
register_source(SourceName.DAEGU_ART_MUSEUM, DaeguArtMuseumExtractor)
