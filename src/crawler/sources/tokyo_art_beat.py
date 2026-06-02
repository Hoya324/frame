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

Venue coords/address: latitude/longitude are populated from venue.fields.geoInfo
so TAB venues skip name-only geocoding; venue_address stays None (the pipeline
geocodes using venue.name via GeocoderResolver → GoogleMapsGeocoder).

Detail-page enrichment (description + artists): the EventSearch list objects
expose no prose field, but the per-event page IS server-rendered — the catch-all
route `/events/-/<slug>` SSRs a second SWR cache entry keyed
`{"name":"EventDetail",...}` whose `data[0]` carries the exhibition's own
top-level `description` string AND an `artists` string (CJK-comma separated).
So when `with_details` is on (the default) we fetch each photo event's detail
page and merge those in. ~85% of photo events ship a real, multi-paragraph
Japanese statement this way — no client-API reverse-engineering needed, contrary
to the earlier list-only assumption. NOTE: `venue.fields.description` also exists
but describes the gallery, not the show, so it is deliberately ignored.
"""

from __future__ import annotations

import json
import re
import time
from collections.abc import Iterable

import httpx
from selectolax.parser import HTMLParser
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

from crawler.models import RawExhibition, SourceName
from crawler.normalize.text import clean_whitespace
from crawler.sources._detail import MIN_DESCRIPTION_LEN
from crawler.sources.base import register_source

_BASE_URL = "https://www.tokyoartbeat.com"
_LIST_URL = f"{_BASE_URL}/events"
_USER_AGENT = "PhotoExhibitionCrawler/0.1 (+contact@example.com)"

_PHOTO_KEYWORDS = ("写真", "フォト", "photography", "photo")

# TAB ships the artist roster as one string joined by CJK/full-width/ASCII commas.
_ARTIST_SEP_RE = re.compile(r"[、，,]")


class TokyoArtBeatExtractor:
    name = SourceName.TOKYO_ART_BEAT
    country = "JP"

    def __init__(
        self,
        timeout_s: float = 30.0,
        with_details: bool = True,
        delay_s: float = 1.0,
    ) -> None:
        # /events is ~2MB so timeout is generous; no per-page pagination —
        # the SSR payload caps at limit=1000 in the SWR call params and we
        # take that as the snapshot for the day. with_details fetches each
        # photo event's detail page for its description+artists, throttled by
        # delay_s to stay polite (~140 photo events per snapshot).
        self.with_details = with_details
        self.delay_s = delay_s
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
            url = row["source_url"]
            payload = {k: v for k, v in row.items() if k != "source_url"}
            if self.with_details:
                try:
                    detail = _extract_detail_from_html(self._get(url))
                    payload.update(_detail_to_fields(detail))
                except Exception:  # noqa: BLE001
                    pass  # list row still ships even if the detail fetch fails
                if self.delay_s > 0:
                    time.sleep(self.delay_s)
            yield RawExhibition(
                source=SourceName.TOKYO_ART_BEAT,
                source_url=url,
                raw=payload,
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
            # The slug is a path fragment (name/id/date); TAB's real event
            # route is /events/-/<slug> — without the "-" segment the catch-all
            # falls back to the generic listing page instead of the event.
            "source_url": f"{_BASE_URL}/events/-/{slug}",
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


def _extract_detail_from_html(html: str) -> dict:
    """Pull the single EventDetail object out of a TAB detail page's __NEXT_DATA__.

    Mirrors _extract_events_from_html but targets the `EventDetail` SWR cache
    entry instead of `EventSearch`. Returns {} if the blob is missing/malformed
    so the caller can treat it as "no enrichment available".
    """
    doc = HTMLParser(html)
    script = doc.css_first("script#__NEXT_DATA__")
    if script is None:
        return {}
    try:
        data = json.loads(script.text())
    except json.JSONDecodeError:
        return {}
    fallback = data.get("props", {}).get("pageProps", {}).get("fallback", {})
    if not isinstance(fallback, dict):
        return {}
    for key, value in fallback.items():
        if '"name":"EventDetail"' in key and isinstance(value, dict):
            rows = value.get("data")
            if isinstance(rows, list) and rows and isinstance(rows[0], dict):
                return rows[0]
    return {}


def _clean_description(text: str) -> str:
    """Collapse intra-line whitespace while preserving paragraph breaks.

    TAB stores the statement as a single string with `\\n` paragraph breaks;
    clean_whitespace alone would flatten those, so we clean per line and rejoin,
    collapsing runs of blank lines to a single break.
    """
    lines = [clean_whitespace(ln) for ln in text.split("\n")]
    out: list[str] = []
    for ln in lines:
        if not ln and (not out or not out[-1]):
            continue  # skip leading/duplicate blank lines
        out.append(ln)
    return "\n".join(out).strip()


def _detail_to_fields(item: dict) -> dict:
    """Extract the exhibition `description` and `artists` from an EventDetail item.

    The description must clear MIN_DESCRIPTION_LEN to count as a real statement;
    venue.fields.description (the gallery blurb) is intentionally not consulted.
    Artists arrive as one comma-joined string and are split into a clean list.
    """
    out: dict = {}

    desc = item.get("description")
    if isinstance(desc, str):
        cleaned = _clean_description(desc)
        if len(cleaned) >= MIN_DESCRIPTION_LEN:
            out["description"] = cleaned

    raw_artists = item.get("artists")
    if isinstance(raw_artists, str):
        names = [n.strip() for n in _ARTIST_SEP_RE.split(raw_artists)]
        names = [n for n in names if n]
        if names:
            out["artists"] = names

    return out


register_source(SourceName.TOKYO_ART_BEAT, TokyoArtBeatExtractor)
