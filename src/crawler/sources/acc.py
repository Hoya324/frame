"""ACC — Asia Culture Center (국립아시아문화전당, 광주) static-HTML extractor.

Strategy: GET the 현재전시 (current exhibitions) list and parse the
server-rendered gallery cards. General culture-complex programming (craft,
history, children's shows, film/video, …) means every card is passed through the
photo/film/media keyword gate; only matching shows are yielded.

URL pattern (verified 2026-07-20):
  List:   GET https://www.acc.go.kr/main/exhibition.do?PID=0202
  Detail: GET https://www.acc.go.kr/main/exhibition.do?PID=0202&action=Read&bnkey=EM_<ID>

RECON DEVIATION: `contents.do?PID=0202` (the URL from the original recon notes)
returns a "콘텐츠 준비중" placeholder page. The real server-rendered list is
`exhibition.do?PID=0202` — linked as the active 현재전시 nav entry.

Card structure (one `<li>` per show inside `div.skedBoardList > ul`):
  <li>
    <a href="?PID=0202&action=Read&bnkey=EM_0000009294"
       onclick="fn_linkToReadWithLink('EM_0000009294','')">
      <div class="thumb"><img src="/resources/upload/....jpg" alt=""></div>
      <p class="tit">ACC 필름앤비디오 <br>《아시아의 장치들》</p>
    </a>
    <p class="cont">무빙이미지를 하나의 장치로 삼아 … 전시</p>       ← curated summary
    <p class="term"><span class="label">일자</span>2026-03-19 ~ 2026-09-27&nbsp;</p>
    <p class="price"><span class="label">가격</span>무료</p>
    <div class="btnBox"><p class="apply2"><span>기획전시</span></p></div>
  </li>

RECON DEVIATION (in our favour): dates ARE on the list (`p.term`,
"YYYY-MM-DD ~ YYYY-MM-DD"), and the title lives in `p.tit` (a text node, with
`<br>` line breaks) — NOT in the banner `<img>` alt, which is empty. The detail
page is still fetched for the long description and labeled fallback fields.

Detail page:
- Labeled `<em>/<span>` pairs in `div.detailTxt ul.txtList li`:
  기간 ("2026.3.19.(목) - 9.27.(일)" → `_detail.extract_date_range`), 장소,
  가격, 시간, … — used as fallbacks when the list lacked a value.
- Long prose in `div.scheduleViewConInfo` — page authors embed `<style>` blocks
  in the CMS content, so style/script nodes are decomposed before text
  extraction. Falls back to the `p.addTxt` summary, then the og:description.
- Poster fallback: og:image meta tag.

Permanent (상설) shows are kept — they carry long explicit ranges on this site.

Media gate: `media_category(title + list summary, detail prose)`. The list
summary (`p.cont`) is a curated one-liner, so broad keywords are safe on it.
Cards like "ACC 필름앤비디오 《아시아의 장치들》" and "자밀 프라이즈: 무빙
이미지" pass; craft/history shows are skipped.

Venue constants: 국립아시아문화전당 / 광주 / 광주광역시 동구 문화전당로 38.

Pagination: `&pageIndex=N` (1-based; plain GET works even though the page's own
pager goes through a JS form submit). 8 cards on page 1 + 4 permanent
children's/archive items on page 2 at recon time. The crawler advances until a
page yields no new card URLs (out-of-range pages re-serve existing cards).

Robots: no restriction on /main/exhibition.do; crawl respectfully (1 s delay).
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
from crawler.sources._detail import (
    MIN_DESCRIPTION_LEN,
    extract_date_range,
    meta_description,
    paragraphs_text,
)
from crawler.sources._media import media_category
from crawler.sources.base import register_source

_BASE = "https://www.acc.go.kr"
_LIST_URL = "https://www.acc.go.kr/main/exhibition.do?PID=0202"
_DETAIL_URL = "https://www.acc.go.kr/main/exhibition.do?PID=0202&action=Read&bnkey={bnkey}"
_USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"
    " (KHTML, like Gecko) Chrome/120.0 Safari/537.36"
)

_VENUE_NAME = "국립아시아문화전당"
_VENUE_REGION = "광주"
_VENUE_ADDRESS = "광주광역시 동구 문화전당로 38"

_BNKEY_RE = re.compile(r"bnkey=(EM_\d+)")
_LIST_DATE_RE = re.compile(r"\d{4}-\d{2}-\d{2}\s*~\s*\d{4}-\d{2}-\d{2}")


class AccExtractor:
    name = SourceName.ACC

    def __init__(
        self,
        max_pages: int = 5,
        delay_s: float = 1.0,
        timeout_s: float = 30.0,
        with_details: bool = True,
    ) -> None:
        self.max_pages = max_pages
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
        seen: set[str] = set()
        for page in range(1, self.max_pages + 1):
            url = _LIST_URL if page == 1 else f"{_LIST_URL}&pageIndex={page}"
            cards = _extract_cards(self._get(url))
            # Out-of-range pages re-serve existing cards: stop when nothing new.
            fresh = [c for c in cards if c["source_url"] not in seen]
            if not fresh:
                return

            for c in fresh:
                detail_url = c["source_url"]
                seen.add(detail_url)
                payload = {k: v for k, v in c.items() if k not in ("source_url", "summary")}
                summary = c.get("summary") or ""

                description: str | None = None
                if self.with_details:
                    # Per-item detail failures must not abort the crawl.
                    try:
                        detail = _parse_detail(self._get(detail_url))
                        description = detail.get("description")
                        # Detail values only fill gaps the list left open.
                        for k, v in detail.items():
                            if payload.get(k) in (None, "", []):
                                payload[k] = v
                            elif k == "description":
                                payload[k] = v
                    except Exception:  # noqa: BLE001
                        pass
                    if self.delay_s > 0:
                        time.sleep(self.delay_s)

                # Media gate: ACC programs mostly non-media shows; keep photo/
                # film/media only. Title + curated summary are the short text.
                category = media_category(f"{payload['title']} {summary}", description)
                if category is None:
                    continue
                payload["category"] = category

                yield RawExhibition(source=SourceName.ACC, source_url=detail_url, raw=payload)

            if self.delay_s > 0:
                time.sleep(self.delay_s)


def _extract_cards(html: str) -> list[dict]:
    """Parse the gallery-style current-exhibition list into card dicts.

    Returns dicts with keys: source_url, title, summary, date_range, venue_name,
    venue_region, venue_address, poster_image_url, artists, and optionally
    fee_text. Scoped to `div.skedBoardList` so footer/webzine junk with similar
    class names is never picked up.
    """
    doc = HTMLParser(html)
    cards: list[dict] = []

    for li in doc.css("div.skedBoardList li"):
        a = li.css_first("a")
        if a is None:
            continue
        m = _BNKEY_RE.search(a.attributes.get("href") or "")
        if not m:
            continue
        bnkey = m.group(1)

        tit = li.css_first("p.tit")
        title = clean_whitespace(tit.text(separator=" ")) if tit else ""
        if not title:
            continue

        cont = li.css_first("p.cont")
        summary = clean_whitespace(cont.text()) if cont else ""

        # "일자" label + "YYYY-MM-DD ~ YYYY-MM-DD" text — regex out the range.
        date_range: str | None = None
        term = li.css_first("p.term")
        if term:
            dm = _LIST_DATE_RE.search(term.text())
            if dm:
                date_range = clean_whitespace(dm.group(0))

        # "가격" label + fee text ("무료" or a ticket-price blurb).
        fee_text: str | None = None
        price = li.css_first("p.price")
        if price:
            label = price.css_first("span.label")
            if label is not None:
                label.decompose()
            fee = clean_whitespace(price.text())
            if fee:
                fee_text = fee

        img = li.css_first("div.thumb img")
        poster: str | None = None
        if img:
            src = img.attributes.get("src") or ""
            if src:
                poster = src if src.startswith("http") else _BASE + src

        card: dict = {
            "source_url": _DETAIL_URL.format(bnkey=bnkey),
            "title": title,
            "summary": summary,
            "date_range": date_range,
            "venue_name": _VENUE_NAME,
            "venue_region": _VENUE_REGION,
            "venue_address": _VENUE_ADDRESS,
            "poster_image_url": poster,
            "artists": [],
        }
        if fee_text:
            card["fee_text"] = fee_text
        cards.append(card)

    return cards


def _parse_detail(html: str) -> dict:
    """Pull description + labeled fallback fields from an ACC detail page."""
    doc = HTMLParser(html)
    out: dict = {}

    # Long prose — CMS content embeds <style> blocks; strip them before text.
    text = ""
    node = doc.css_first("div.scheduleViewConInfo")
    if node is not None:
        for junk in node.css("style,script"):
            junk.decompose()
        text = paragraphs_text(node)
    if len(text) < MIN_DESCRIPTION_LEN:
        add = doc.css_first("p.addTxt")
        alt = clean_whitespace(add.text()) if add else ""
        text = alt if len(alt) >= MIN_DESCRIPTION_LEN else (meta_description(doc) or text)
    if len(text) >= MIN_DESCRIPTION_LEN:
        out["description"] = text

    # Labeled <em>label</em><span>value</span> rows: 기간 / 가격 / 장소 / ….
    for li in doc.css("div.detailTxt ul.txtList li"):
        em = li.css_first("em")
        span = li.css_first("span")
        if em is None or span is None:
            continue
        label = em.text(strip=True)
        value = clean_whitespace(span.text(separator=" "))
        if label == "기간" and value:
            canonical = extract_date_range(value)
            if canonical:
                out["date_range"] = canonical
        elif label == "가격" and value:
            out["fee_text"] = value

    og = doc.css_first('meta[property="og:image"]')
    if og is not None and og.attributes.get("content"):
        out["poster_image_url"] = og.attributes["content"]

    return out


# Register on import
register_source(SourceName.ACC, AccExtractor)
