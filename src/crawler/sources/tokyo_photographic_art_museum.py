"""東京都写真美術館 (Tokyo Photographic Art Museum) — list extractor.

Source: https://topmuseum.jp/exhibition/ — WordPress-based site. The
landing page renders every current+upcoming exhibition as a
`div.slider__item` card. Cards whose class also contains "-movie" are
video clip embeds, not exhibitions, and are skipped.

Card structure (verified 2026-05-28):
  <div class="slider__item">
    <a href="https://topmuseum.jp/exhibition/<id>/">
      <div class="slider__img"><img src="..." alt="..."></div>
      <dl class="slider__cell">
        <dt>
          <em class="main">{title}</em>
          <em class="sub">{optional subtitle}</em>
        </dt>
        <dd>
          <em> {floor designation, e.g. "3F 展示室"} </em>
          {start_date}<span class="js-holiday-date" ...>（曜日）</span>
          ～
          {end_date}<span class="js-holiday-date" ...>（曜日）</span>
        </dd>
      </dl>
    </a>
  </div>

The museum runs 3-5 simultaneous photo/video exhibitions across B1F,
2F, and 3F floors. All exhibitions are photography-related (the museum
is dedicated to it) so no category whitelist is needed.

Venue address verified against the museum's contact page:
東京都目黒区三田1-13-3 恵比寿ガーデンプレイス内
"""

from __future__ import annotations

import time
from collections.abc import Iterable
from urllib.parse import urljoin

import httpx
from selectolax.parser import HTMLParser
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

from crawler.models import RawExhibition, SourceName
from crawler.sources.base import register_source

_BASE_URL = "https://topmuseum.jp"
_LIST_URL = f"{_BASE_URL}/exhibition/"
_USER_AGENT = "PhotoExhibitionCrawler/0.1 (+contact@example.com)"

_VENUE_NAME = "東京都写真美術館"
_VENUE_NAME_EN = "Tokyo Photographic Art Museum"
_VENUE_REGION = "東京都"
_VENUE_ADDRESS = "東京都目黒区三田1-13-3 恵比寿ガーデンプレイス内"


class TokyoPhotographicArtMuseumExtractor:
    name = SourceName.TOKYO_PHOTOGRAPHIC_ART_MUSEUM
    country = "JP"

    def __init__(self, delay_s: float = 1.0, timeout_s: float = 20.0) -> None:
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
        html = self._get(_LIST_URL)
        for row in _extract_exhibitions(html):
            yield RawExhibition(
                source=SourceName.TOKYO_PHOTOGRAPHIC_ART_MUSEUM,
                source_url=row["source_url"],
                raw={k: v for k, v in row.items() if k != "source_url"},
            )
            if self.delay_s > 0:
                time.sleep(self.delay_s)


def _extract_exhibitions(html: str) -> list[dict]:
    """Parse the TOP listing page into card dicts.

    Returns one dict per UNIQUE exhibition (deduped on source_url) with:
        source_url, title, title_en?, venue_name, venue_name_en,
        venue_region, venue_address, date_range, poster_image_url, artists
    """
    doc = HTMLParser(html)
    out: list[dict] = []
    seen: set[str] = set()

    for card in doc.css("div.slider__item"):
        cls = card.attributes.get("class") or ""
        if "-movie" in cls:
            continue  # video thumbnail, not an exhibition card

        link = card.css_first("a[href]")
        if not link:
            continue
        href = link.attributes.get("href", "")
        if not href:
            continue
        if href.startswith("/"):
            href = urljoin(_BASE_URL, href)
        if href in seen:
            continue

        title_el = card.css_first("dl.slider__cell dt em.main")
        title = title_el.text(strip=True) if title_el else ""
        if not title:
            continue

        seen.add(href)

        # Subtitle (em.sub) usually empty, but capture if present.
        sub_el = card.css_first("dl.slider__cell dt em.sub")
        subtitle = sub_el.text(strip=True) if sub_el else ""

        # The <dd> contains a leading <em> with floor info, then the
        # date range. Pull date_range by taking dd's text and dropping
        # the floor <em>'s text. The js-holiday-date <span>s carry the
        # day-of-week characters in parens — drop those too.
        dd = card.css_first("dl.slider__cell dd")
        date_range: str | None = None
        if dd is not None:
            for floor in dd.css("em"):
                floor.decompose()  # remove the floor designation
            for span in dd.css("span.js-holiday-date"):
                span.decompose()  # remove day-of-week markers
            raw_date = dd.text(strip=True)
            # Collapse any internal whitespace runs to a single space.
            date_range = " ".join(raw_date.split()) or None

        img = card.css_first("div.slider__img img")
        poster = None
        if img is not None:
            src = img.attributes.get("src") or ""
            if src.startswith("/"):
                poster = urljoin(_BASE_URL, src)
            elif src:
                poster = src

        out.append({
            "source_url": href,
            "title": title,
            "title_en": subtitle if subtitle else None,
            "venue_name": _VENUE_NAME,
            "venue_name_en": _VENUE_NAME_EN,
            "venue_region": _VENUE_REGION,
            "venue_address": _VENUE_ADDRESS,
            "date_range": date_range,
            "poster_image_url": poster if poster else None,
            "artists": [],
        })

    return out


register_source(SourceName.TOKYO_PHOTOGRAPHIC_ART_MUSEUM, TokyoPhotographicArtMuseumExtractor)
