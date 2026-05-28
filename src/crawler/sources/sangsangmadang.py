"""KT&G 상상마당 (sangsangmadang.com) — exhibition list extractor.

Strategy: Walk paginated POST requests to /display/selectDisplayList/HD/all.
The site's exhibition list page is entirely AJAX-driven: the static HTML shell
calls a Spring MVC JSON endpoint, which returns a JSON payload with a
``displayListInfo.displayList`` array.  We call this JSON API directly.

Whitelist (spec §3, card-level filter):
  The site has no dedicated photo category.  ``cdVal`` (genre) values are
  '시각예술', '기획전시', '직접입력', '디자인', '대관' — none specific to
  photography.  The only reliable photo signal is the exhibition title.
  Cards whose title contains one of (_PHOTO_KEYWORDS) are emitted; all others
  are silently dropped.

Branch / venue handling:
  The API exposes ``spaceCd`` per item (HD/NS/CC/DC/BS).  We scrape only the
  HD (홍대) endpoint, so spaceCd is always 'HD'.  Future expansion to other
  branches can be achieved by parameterising the URL spaceCd and using
  _SPACE_VENUE / _SPACE_REGION maps defined below.

Space code → venue/region mapping (from live site verified 2026-05-28):
  HD (Hongdae)   → 홍대,  서울
  NS (Nonsan)    → 논산,  충남
  CC (Chuncheon) → 춘천,  강원도
  DC (Daechi)    → 대치,  서울
  BS (Busan)     → 부산,  부산

Domain note: the plan listed 홍대/논현/부산/춘천 as branches.  The live site
(verified 2026-05-28) uses 홍대/논산/춘천/대치/부산 — '논현' does not exist;
'논산' (Nonsan, South Chungcheong) is the correct second branch.

Detail URL is /display/detail/{contentsSeq} (GET).  The detail page itself is
largely static HTML; all structured data needed (title, term, venue, poster)
is already present in the list-API response, so we do not fetch detail pages.

Pagination: stop when ``displayListInfo.displayList`` is empty.
"""

from __future__ import annotations

import html as html_mod
import time
from collections.abc import Iterable

import httpx
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

from crawler.models import RawExhibition, SourceName
from crawler.sources.base import register_source

_BASE_URL = "https://www.sangsangmadang.com"
_LIST_URL = f"{_BASE_URL}/display/selectDisplayList/HD/all"
_USER_AGENT = "PhotoExhibitionCrawler/0.1 (+contact@example.com)"

# Default venue constants (홍대 branch)
_DEFAULT_VENUE_NAME = "KT&G 상상마당 홍대 갤러리"
_DEFAULT_VENUE_REGION = "서울"

# Space-code → (branch label, venue name, region)
_SPACE_INFO: dict[str, tuple[str, str, str]] = {
    "HD": ("홍대", "KT&G 상상마당 홍대 갤러리", "서울"),
    "NS": ("논산", "KT&G 상상마당 논산 갤러리", "충남"),
    "CC": ("춘천", "KT&G 상상마당 춘천 갤러리", "강원도"),
    "DC": ("대치", "KT&G 상상마당 대치 갤러리", "서울"),
    "BS": ("부산", "KT&G 상상마당 부산 갤러리", "부산"),
}

# Source-level photo whitelist keywords (spec §3, option B — card-level filter)
_PHOTO_KEYWORDS = ("사진", "포토", "photo", "Photo", "PHOTO")


def _is_photo_card(title: str) -> bool:
    """Return True when an exhibition title contains a photo keyword."""
    return any(kw in title for kw in _PHOTO_KEYWORDS)


class SangsangmadangExtractor:
    name = SourceName.SANGSANGMADANG

    def __init__(
        self,
        max_pages: int = 30,
        delay_s: float = 1.0,
        timeout_s: float = 20.0,
    ) -> None:
        self.max_pages = max_pages
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
    def _post(self, url: str, data: dict) -> dict:
        r = self._client.post(url, data=data)
        r.raise_for_status()
        return r.json()

    def crawl(self) -> Iterable[RawExhibition]:
        seen: set[str] = set()
        for page_num in range(1, self.max_pages + 1):
            payload = {"spaceCd": "HD", "status": "all", "page": str(page_num)}
            response = self._post(_LIST_URL, payload)
            cards = _extract_cards(response)
            if not cards:
                return

            for c in cards:
                card_url = c["source_url"]
                if card_url in seen:
                    continue
                seen.add(card_url)
                yield RawExhibition(
                    source=SourceName.SANGSANGMADANG,
                    source_url=card_url,
                    raw={k: v for k, v in c.items() if k != "source_url"},
                )

            if self.delay_s > 0:
                time.sleep(self.delay_s)


def _extract_cards(response: dict) -> list[dict]:
    """Parse a JSON API response and return photo-exhibition card dicts.

    Only cards whose title matches _PHOTO_KEYWORDS are returned (whitelist).

    Keys: source_url, title, venue_name, venue_region, date_range,
    poster_image_url.  Artists are omitted — they do not appear in list data.
    """
    try:
        items = response["displayListInfo"]["displayList"]
    except (KeyError, TypeError):
        return []

    cards: list[dict] = []
    for item in items:
        raw_title: str = item.get("title", "")
        title = html_mod.unescape(raw_title).strip()
        if not title:
            continue

        # Photo whitelist: skip non-photo exhibitions
        if not _is_photo_card(title):
            continue

        seq: int | str | None = item.get("contentsSeq")
        if not seq:
            continue
        source_url = f"{_BASE_URL}/display/detail/{seq}"

        # Venue from spaceCd
        space_cd: str = item.get("spaceCd", "HD")
        _, venue_name, venue_region = _SPACE_INFO.get(
            space_cd, ("홍대", _DEFAULT_VENUE_NAME, _DEFAULT_VENUE_REGION)
        )

        # Date range
        date_range: str | None = item.get("term") or None

        # Poster image URL
        poster: str | None = item.get("posterFilePath") or None

        cards.append({
            "source_url": source_url,
            "title": title,
            "venue_name": venue_name,
            "venue_region": venue_region,
            "date_range": date_range,
            "poster_image_url": poster,
        })

    return cards


register_source(SourceName.SANGSANGMADANG, SangsangmadangExtractor)
