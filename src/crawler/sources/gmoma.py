"""경기도미술관 (Gyeonggi Museum of Modern Art, gmoma.ggcf.kr) — HTML extractor.

Strategy (recon 2026-07-20): GET /exhibitions?progress=now and ?progress=yet
(current + upcoming). Both are single server-rendered pages on the shared
ggcf.kr CMS (same platform as 백남준아트센터) — no pagination.

List structure (verified 2026-07-20): ONE `li.item-list` container per page
wraps every card (NOT one `<li>` per card):

  <li class="item-list">
    <div>
      <a href="/exhibitions/206">
        <div class="img-box"><img src="/storage/upload/…jpg" alt=""></div>
        <p>《우리의 여름에게》</p>
        <p class="date"> 2026. 07. 16. — 2026. 09. 27. </p>
      </a>
    </div>
    <div>…next card…</div>
  </li>

An empty `?progress=yet` renders the bare `li.item-list` with no anchors.

Dates use dotted parts with an em-dash ("2026. 07. 16. — 2026. 09. 27.");
`_detail.extract_date_range` canonicalizes them. The permanent collection
show is OPEN-ENDED ("2023. 09. 15. — " with no end) — extract_date_range
returns None there, and `date_range=None` is fine downstream.

Detail page (`/exhibitions/{id}`):
  - prose in `div.view-content` (more precise than `div.content`, which on
    some pages also swallows site chrome); meta-description fallback;
  - a `<dl>` metadata block whose `참여작가` row lists artists
    (comma-separated; group names may carry a parenthesised member roster,
    so the split is paren-aware);
  - `og:image` is empty today (poster stays the list thumbnail).

Media gate: GMoMA is a general contemporary-art museum, so each card passes
the shared photo/film/media keyword gate (:mod:`crawler.sources._media`):
broad keywords over the title, strict compounds over the detail description.
Most shows are NOT photo/media — 0 yields from a live run is the filter
working, not a parser fault.

Robots: no robots.txt restriction found; crawl respectfully (1 s delay).
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

_BASE_URL = "https://gmoma.ggcf.kr"
_LIST_URL = f"{_BASE_URL}/exhibitions"
_USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Safari/537.36"
)

# progress values we crawl: current + upcoming.
_PROGRESS_VALUES = ("now", "yet")

_VENUE_NAME = "경기도미술관"
_VENUE_REGION = "경기"
_VENUE_ADDRESS = "경기도 안산시 단원구 동산로 268"

# Detail hrefs look like /exhibitions/206 (relative) — nothing deeper.
_DETAIL_HREF_RE = re.compile(r"^(?:https?://gmoma\.ggcf\.kr)?/exhibitions/\d+$")


def _split_artists(text: str) -> list[str]:
    """Split a 참여작가 roster on top-level commas.

    Group entries carry a parenthesised member list — e.g.
    "송석우, 알오에스(강류, 김시월, 심다은, 유다영)" — so commas inside
    parens must not split.
    """
    names: list[str] = []
    depth = 0
    buf: list[str] = []
    for ch in text:
        if ch in "(（":
            depth += 1
        elif ch in ")）":
            depth = max(0, depth - 1)
        if ch in ",、·" and depth == 0:
            names.append("".join(buf))
            buf = []
        else:
            buf.append(ch)
    names.append("".join(buf))
    # Anything longer than a name is a stray clause, not an artist.
    return [n for n in (clean_whitespace(n) for n in names) if n and len(n) <= 40]


class GmomaExtractor:
    name = SourceName.GMOMA
    country = "KR"

    def __init__(
        self,
        delay_s: float = 1.0,
        timeout_s: float = 20.0,
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
    def _get_list(self, progress: str) -> str:
        r = self._client.get(_LIST_URL, params={"progress": progress})
        r.raise_for_status()
        return r.text

    @retry(
        retry=retry_if_exception_type(httpx.TransportError),
        wait=wait_exponential(multiplier=1, min=1, max=16),
        stop=stop_after_attempt(3),
        reraise=True,
    )
    def _get_url(self, url: str) -> str:
        r = self._client.get(url)
        r.raise_for_status()
        return r.text

    def crawl(self) -> Iterable[RawExhibition]:
        seen: set[str] = set()
        for progress in _PROGRESS_VALUES:
            for c in _extract_cards(self._get_list(progress)):
                url = c["source_url"]
                if url in seen:
                    continue
                seen.add(url)
                payload = {k: v for k, v in c.items() if k != "source_url"}

                # The detail description feeds the strict tier of the media
                # gate, so it is fetched BEFORE filtering. A failed fetch
                # falls back to gating on the title alone.
                if self.with_details:
                    try:
                        payload.update(_parse_detail(self._get_url(url)))
                    except Exception:  # noqa: BLE001 — partial data beats aborting
                        pass
                    if self.delay_s > 0:
                        time.sleep(self.delay_s)

                # Photo/film/media gate: broad keywords over the title,
                # strict compounds over the detail description.
                category = media_category(
                    payload["title"], payload.get("description")
                )
                if category is None:
                    continue
                payload["category"] = category

                yield RawExhibition(
                    source=SourceName.GMOMA,
                    source_url=url,
                    raw=payload,
                )

            if self.delay_s > 0:
                time.sleep(self.delay_s)


def _extract_cards(html: str) -> list[dict]:
    """Parse an /exhibitions?progress=… page into card dicts (pre-media-gate).

    Returns dicts with keys: source_url, title, date_range, venue_name,
    venue_region, venue_address, poster_image_url, artists.
    """
    doc = HTMLParser(html)
    cards: list[dict] = []

    for a in doc.css("li.item-list a"):
        href = a.attributes.get("href") or ""
        if not _DETAIL_HREF_RE.match(href):
            continue

        source_url = href if href.startswith("http") else _BASE_URL + href

        # Title: the <p> WITHOUT the "date" class (usually 《…》-wrapped).
        title = ""
        date_text = ""
        for p in a.css("p"):
            classes = p.attributes.get("class") or ""
            if "date" in classes.split():
                date_text = p.text(strip=True)
            elif not title:
                title = p.text(strip=True)
        if not title:
            continue

        # Open-ended permanent shows ("2023. 09. 15. — ") yield None here.
        date_range = extract_date_range(date_text) if date_text else None

        # Thumbnail — div.img-box img (relative /storage/upload path)
        poster: str | None = None
        img = a.css_first("div.img-box img")
        if img:
            src = img.attributes.get("src") or ""
            if src:
                poster = src if src.startswith("http") else _BASE_URL + src

        cards.append({
            "source_url": source_url,
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
    """Pull description / artists from a GMoMA detail page.

    Prose sits in `div.view-content` (`div.content` swallows site chrome on
    some pages); the `<dl>` metadata block carries a `참여작가` row.
    """
    doc = HTMLParser(html)
    out: dict = {}

    body = doc.css_first("div.view-content")
    text = paragraphs_text(body) if body is not None else ""
    if len(text) < MIN_DESCRIPTION_LEN:
        text = meta_description(doc) or text
    if len(text) >= MIN_DESCRIPTION_LEN:
        out["description"] = text

    # dl metadata: <dt>참여작가</dt><dd><p>강익중, 권기수, …</p></dd>
    for dl in doc.css("dl"):
        dts = dl.css("dt")
        dds = dl.css("dd")
        for dt, dd in zip(dts, dds, strict=False):
            if "참여작가" in dt.text(strip=True):
                artists = _split_artists(dd.text(strip=True))
                if artists:
                    out["artists"] = artists
                break

    return out


# Register on import
register_source(SourceName.GMOMA, GmomaExtractor)
