"""Tokyo Art Beat (tokyoartbeat.com) — photography category list extractor.

Strategy (recon 2026-05-28):
TAB renders its events list via a Next.js SPA, but the /events page is
SSR'd: the `<script id="__NEXT_DATA__">` carries a fully populated SWR
fallback cache with up to 1000 events under the "EventSearch" entry.
No JS rendering or API reverse-engineering required.

Pipeline:
1. GET /events (httpx, default UA + Accept-Language) → HTML
2. Parse the script tag JSON, locate the EventSearch cache entry
   (its key is the stringified call params, so we scan keys)
3. Filter the data list by categories[].fields.name containing one of
   "写真", "Photography", "フォト" — TAB is multi-medium, so the
   whitelist is mandatory at the source level (same pattern as
   sangsangmadang for Korean expansion)
4. Map each event to the RawExhibition raw shape

Detail-page enrichment is intentionally out of scope for the first
iteration. Artists come back as []; venue_address as None (the pipeline
will geocode using venue.name via GeocoderResolver → GoogleMapsGeocoder).
A future enhancement can populate latitude/longitude from
venue.fields.geoInfo to skip geocoding for TAB venues entirely.
"""

from __future__ import annotations

import json
from collections.abc import Iterable

import httpx
from selectolax.parser import HTMLParser
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

from crawler.models import RawExhibition, SourceName
from crawler.sources.base import register_source

_BASE_URL = "https://www.tokyoartbeat.com"
_LIST_URL = f"{_BASE_URL}/events"
_USER_AGENT = "PhotoExhibitionCrawler/0.1 (+contact@example.com)"

_PHOTO_KEYWORDS = ("写真", "フォト", "photography", "photo")


class TokyoArtBeatExtractor:
    name = SourceName.TOKYO_ART_BEAT
    country = "JP"

    def __init__(self, timeout_s: float = 30.0) -> None:
        # /events is ~2MB so timeout is generous; no per-page pagination —
        # the SSR payload caps at limit=1000 in the SWR call params and we
        # take that as the snapshot for the day.
        self._client = httpx.Client(
            timeout=timeout_s,
            headers={
                "User-Agent": _USER_AGENT,
                "Accept-Language": "en-US,en;q=0.9,ja;q=0.8",
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
        return r.text

    def crawl(self) -> Iterable[RawExhibition]:
        html = self._get(_LIST_URL)
        events = _extract_events_from_html(html)
        for row in _events_to_rows(events):
            yield RawExhibition(
                source=SourceName.TOKYO_ART_BEAT,
                source_url=row["source_url"],
                raw={k: v for k, v in row.items() if k != "source_url"},
            )


def _extract_events_from_html(html: str) -> list[dict]:
    """Pull the events list out of TAB's SSR'd __NEXT_DATA__ blob.

    Returns the raw event list (no filtering, no shape conversion).
    Empty list if anything is missing — caller can treat it as "no
    events", same as if the SWR cache was empty.
    """
    doc = HTMLParser(html)
    script = doc.css_first("script#__NEXT_DATA__")
    if script is None:
        return []
    try:
        data = json.loads(script.text())
    except json.JSONDecodeError:
        return []
    fallback = data.get("props", {}).get("pageProps", {}).get("fallback", {})
    if not isinstance(fallback, dict):
        return []
    for key, value in fallback.items():
        # Keys are stringified SWR call params; the events list lives
        # under the EventSearch entry. There's only ever one.
        if '"name":"EventSearch"' in key and isinstance(value, dict):
            events = value.get("data")
            if isinstance(events, list):
                return events
    return []


def _is_photography(event: dict) -> bool:
    """True if any of the event's categories matches a photography keyword."""
    cats = event.get("categories") or []
    for c in cats:
        name = (c.get("fields") or {}).get("name") or ""
        if not name:
            continue
        lower = name.lower()
        for kw in _PHOTO_KEYWORDS:
            if kw in name or kw in lower:
                return True
    return False


def _events_to_rows(events: list[dict]) -> list[dict]:
    """Filter to photo events and convert each to a RawExhibition raw dict."""
    out: list[dict] = []
    for ev in events:
        if not _is_photography(ev):
            continue
        slug = ev.get("slug")
        if not slug:
            continue
        title = ev.get("eventName") or ""
        if not title:
            continue

        venue = (ev.get("venue") or {}).get("fields") or {}
        venue_name = venue.get("fullName") or ""
        if not venue_name:
            continue

        local_area = (venue.get("localArea") or {}).get("fields") or {}
        venue_region = local_area.get("name")  # may be None

        # TAB ships exact venue coordinates in the payload — use them directly
        # so the pipeline can skip name-only geocoding, which fails for the
        # many small galleries TAB lists (e.g. "PURPLE", "PGI").
        geo = venue.get("geoInfo") or {}
        venue_lat = geo.get("lat")
        venue_lng = geo.get("lon")

        starts = ev.get("scheduleStartsOn")
        ends = ev.get("scheduleEndsOn")
        date_range = (
            f"{starts} ~ {ends}" if starts and ends
            else (starts or ends or None)
        )

        poster_url = None
        img = (ev.get("imageposter") or {}).get("fields") or {}
        file_obj = img.get("file") or {}
        raw_url = file_obj.get("url")
        if raw_url:
            poster_url = (
                f"https:{raw_url}" if raw_url.startswith("//") else raw_url
            )

        out.append({
            "source_url": f"{_BASE_URL}/events/{slug}",
            "title": title,
            "venue_name": venue_name,
            "venue_region": venue_region,
            "venue_address": None,
            "venue_lat": venue_lat,
            "venue_lng": venue_lng,
            "date_range": date_range,
            "poster_image_url": poster_url,
            "artists": [],
        })
    return out


register_source(SourceName.TOKYO_ART_BEAT, TokyoArtBeatExtractor)
