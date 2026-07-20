"""국립현대미술관 (MMCA, mmca.go.kr) — JSON API extractor.

Strategy (recon 2026-07-20):
The public list page ``/exhibitions/progressList.do`` renders its cards via a
jQuery ``$.ajax`` call; the underlying data source is a clean JSON endpoint:

  GET /exhibitions/AjaxExhibitionList.do
    ?exhFlag=1|2|3          1 = ongoing, 2 = upcoming, 3 = past (~1,300 rows)
    &pageIndex=N            1-based; paginationInfo.totalPageCount pages, 8/page
    &searchExhPlaCd=&searchExhCd=&sort=1

We crawl ongoing (1) + upcoming (2). Every field we need is in the list JSON —
title, ISO date range, artists, venue branch, admission, thumbnail, the
museum's own genre code (``exhCd``/``exhTpCd``, e.g. "필름앤비디오"), theme
keywords (``exhThemewd``), a one-line summary (``exhContentsSumm``) and the
full HTML body (``exhContents``) — so no per-exhibition detail fetch is
needed.

MMCA is a general art museum (mostly painting/sculpture), so records pass the
shared photo/film/media keyword gate (:mod:`crawler.sources._media`): broad
keywords over the curated short fields (title + genre code + theme keywords +
summary), strict compounds over the long HTML body. Expect few yields per run
— that is the filter working, not a parser fault.

Detail URL: the site's own JS submits a POST form (``fn_Detail``), but a plain
GET works and renders the same page:

  /exhibitions/exhibitionsDetail.do?exhFlag={flag}&exhId={exhId}

Venue mapping: ``exhPlaNm`` ∈ {서울, 과천, 덕수궁, 청주, 어린이미술관} → branch
constants below (어린이미술관 lives inside the 과천 campus).
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
from crawler.sources._media import media_category
from crawler.sources.base import register_source

_BASE_URL = "https://www.mmca.go.kr"
_AJAX_URL = f"{_BASE_URL}/exhibitions/AjaxExhibitionList.do"
_DETAIL_URL = f"{_BASE_URL}/exhibitions/exhibitionsDetail.do"
_USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Safari/537.36"
)

# exhFlag values we crawl: ongoing + upcoming (past is ~1,300 rows of history).
_FLAGS = (1, 2)

# exhPlaNm → (venue_name, region, address). 어린이미술관 is on the 과천 campus.
_VENUES: dict[str, tuple[str, str, str]] = {
    "서울": ("국립현대미술관 서울", "서울", "서울특별시 종로구 삼청로 30"),
    "과천": ("국립현대미술관 과천", "경기", "경기도 과천시 광명로 313"),
    "덕수궁": ("국립현대미술관 덕수궁", "서울", "서울특별시 중구 세종대로 99"),
    "청주": ("국립현대미술관 청주", "충북", "충청북도 청주시 청원구 상당로 314"),
    "어린이미술관": (
        "국립현대미술관 과천 어린이미술관", "경기", "경기도 과천시 광명로 313",
    ),
}
_DEFAULT_VENUE = ("국립현대미술관", "서울", None)

# "A, B, C 등 40여 명" — trailing headcount clause after a name list. The
# leading \s+ keeps names that merely contain 등/명 (e.g. 홍등명) intact, and
# 팀 covers "… 등 3팀" rosters.
_HEADCOUNT_TAIL_RE = re.compile(r"\s+(?:등|외)\s*[\d,]*\s*여?\s*[명팀].*$")
# A bare headcount ("9인", "73명") with no actual names.
_BARE_HEADCOUNT_RE = re.compile(r"^\d+\s*여?\s*[인명]$")
# "3,000원" — admission amount inside exhAdm free text.
_ADM_AMOUNT_RE = re.compile(r"([\d,]+)\s*원")


class _BadResponse(Exception):
    """A 2xx response whose body is not the expected JSON object.

    Mirrors gallery_bresson: government hosts occasionally return a 200 with
    an HTML error/maintenance body, which is transient and worth retrying.
    """


def _parse_artists(text: str | None) -> list[str]:
    """Split ``exhArtist`` into names; drop headcounts and et-al. tails.

    "-" and bare headcounts ("9인") carry no names. Long rosters end in
    "… 등 40여 명" which we strip before splitting on commas.
    """
    t = clean_whitespace(text or "")
    if not t or t in {"-", "–"} or _BARE_HEADCOUNT_RE.fullmatch(t):
        return []
    t = _HEADCOUNT_TAIL_RE.sub("", t)
    names = [clean_whitespace(n) for n in t.split(",")]
    # Anything longer than a name is a stray clause, not an artist.
    return [n for n in names if n and len(n) <= 30]


def _parse_record(rec: dict) -> dict | None:
    """Map one AjaxExhibitionList record to a RawExhibition raw dict.

    Returns None when the record has no usable title or fails the
    photo/film/media gate.
    """
    title = clean_whitespace(rec.get("exhTitle") or "")
    if not title:
        return None

    summary = clean_whitespace(rec.get("exhContentsSumm") or "")
    body_html = rec.get("exhContents") or ""
    body = clean_whitespace(HTMLParser(body_html).text()) if body_html else ""

    # Curated short fields: title + the museum's own genre code + theme
    # keywords + one-line summary. The long HTML body only counts via the
    # strict compound tier.
    short_text = " ".join(
        filter(
            None,
            [
                title,
                clean_whitespace(rec.get("exhCd") or ""),
                clean_whitespace(rec.get("exhTpCd") or ""),
                clean_whitespace(rec.get("exhThemewd") or ""),
                summary,
            ],
        )
    )
    category = media_category(short_text, body)
    if category is None:
        return None

    start = clean_whitespace(rec.get("exhStDt") or "")
    end = clean_whitespace(rec.get("exhEdDt") or "")
    date_range = f"{start}~{end}" if start and end else (start or None)

    venue_name, region, address = _VENUES.get(
        clean_whitespace(rec.get("exhPlaNm") or ""), _DEFAULT_VENUE
    )

    thumb = clean_whitespace(rec.get("exhThumbImg") or "")
    poster = (
        thumb if thumb.startswith("http") else f"{_BASE_URL}{thumb}"
    ) if thumb else None

    # Admission: "0" / 무료 → free; an explicit ₩ amount seeds the price
    # fields; "-" means unspecified (leave everything unset → FREE default).
    adm = clean_whitespace(rec.get("exhAdm") or "")
    fee_text = None
    price_min = price_max = None
    price_notes = None
    if adm in {"0", "무료"} or "무료" in adm:
        fee_text = "무료"
    else:
        m = _ADM_AMOUNT_RE.search(adm)
        if m:
            amount = int(m.group(1).replace(",", ""))
            price_min = price_max = amount
            price_notes = adm

    raw: dict = {
        "title": title,
        "category": category,
        "date_range": date_range,
        "venue_name": venue_name,
        "venue_region": region,
        "venue_address": address,
        "poster_image_url": poster,
        "description": body if len(body) >= len(summary) else (summary or None),
        "artists": _parse_artists(rec.get("exhArtist")),
    }
    if fee_text:
        raw["fee_text"] = fee_text
    if price_min is not None:
        raw["price_min"] = price_min
        raw["price_max"] = price_max
        raw["price_notes"] = price_notes
    return raw


class MmcaExtractor:
    name = SourceName.MMCA
    country = "KR"

    def __init__(
        self,
        max_pages: int = 10,
        delay_s: float = 1.0,
        timeout_s: float = 20.0,
    ) -> None:
        self.max_pages = max_pages
        self.delay_s = delay_s
        self._client = httpx.Client(
            timeout=timeout_s,
            headers={
                "User-Agent": _USER_AGENT,
                "Accept": "application/json",
                "Accept-Language": "ko,en-US;q=0.8,en;q=0.7",
                "Referer": f"{_BASE_URL}/exhibitions/progressList.do",
            },
            follow_redirects=True,
        )

    @retry(
        retry=retry_if_exception_type((httpx.TransportError, _BadResponse)),
        wait=wait_exponential(multiplier=1, min=1, max=16),
        stop=stop_after_attempt(3),
        reraise=True,
    )
    def _get_page(self, flag: int, page: int) -> dict:
        r = self._client.get(
            _AJAX_URL,
            params={
                "exhFlag": str(flag),
                "pageIndex": str(page),
                "searchExhPlaCd": "",
                "searchExhCd": "",
                "sort": "1",
            },
        )
        r.raise_for_status()
        try:
            data = r.json()
        except ValueError as exc:
            raise _BadResponse(f"non-JSON body ({len(r.content)} bytes)") from exc
        if not isinstance(data, dict):
            raise _BadResponse(f"unexpected JSON shape: {type(data).__name__}")
        return data

    def crawl(self) -> Iterable[RawExhibition]:
        seen: set[str] = set()
        for flag in _FLAGS:
            for page in range(1, self.max_pages + 1):
                data = self._get_page(flag, page)
                records = data.get("exhibitionsList") or []
                if not records:
                    break

                for rec in records:
                    exh_id = str(rec.get("exhId") or "")
                    if not exh_id or exh_id in seen:
                        continue
                    seen.add(exh_id)
                    raw = _parse_record(rec)
                    if raw is None:
                        continue
                    yield RawExhibition(
                        source=SourceName.MMCA,
                        source_url=(
                            f"{_DETAIL_URL}?exhFlag={flag}&exhId={exh_id}"
                        ),
                        raw=raw,
                    )

                total_pages = int(
                    (data.get("paginationInfo") or {}).get("totalPageCount") or 1
                )
                if page >= total_pages:
                    break
                if self.delay_s > 0:
                    time.sleep(self.delay_s)


register_source(SourceName.MMCA, MmcaExtractor)
