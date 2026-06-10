"""Wikimedia Commons client (public-domain files). Free, no API key.

Commons is the source of last resort that actually works for Japanese and
Korean early photography: the Met flags most of its photography images as
not-open-access, and AIC has near-zero coverage there. It is also where the
rehost step already points AIC images, so works sourced here hotlink reliably
from any origin and skip rehosting entirely.

``object_ids`` are exact file titles (``File:Foo.jpg``); ``query`` is a
namespace-6 full-text search filtered to public-domain image files whose
title/artist matches the seed's artist needle."""

from __future__ import annotations

import html
import logging
import re

import httpx
from tenacity import retry, stop_after_attempt, wait_exponential

from crawler.masters.models import RawWork

logger = logging.getLogger(__name__)

_API = "https://commons.wikimedia.org/w/api.php"
_UA = "frame-photo/1.0 (hoyana1225@gmail.com)"
# NOTE: serve the API-rendered thumburl as-is — Wikimedia rejects hand-edited
# width/filename combinations (HTTP 400), and originals can be huge TIFFs.
_WIDTH = 1200


def _strip_html(s: str) -> str:
    return re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", s))).strip()


def _is_pd(extmeta: dict) -> bool:
    lic = (extmeta.get("LicenseShortName", {}).get("value") or "").lower()
    return "public domain" in lic or "cc0" in lic or "pd-" in lic


def _title_of(page: dict, extmeta: dict) -> str:
    obj = _strip_html(extmeta.get("ObjectName", {}).get("value") or "")
    if 0 < len(obj) <= 120:
        return obj
    name = re.sub(r"^File:", "", page.get("title") or "")
    name = re.sub(r"\.[A-Za-z]{3,4}$", "", name).replace("_", " ").strip()
    return name or "Untitled"


def _year_of(extmeta: dict) -> str | None:
    raw = _strip_html(extmeta.get("DateTimeOriginal", {}).get("value") or "")
    m = re.search(r"\b(1[89]\d\d)\b", raw)
    return m.group(1) if m else None


class CommonsClient:
    source = "wikimedia"

    def __init__(self, client: httpx.Client | None = None) -> None:
        self._client = client or httpx.Client(timeout=40.0, headers={"User-Agent": _UA})

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(max=10), reraise=True)
    def _get(self, params: dict) -> dict:
        r = self._client.get(_API, params={"action": "query", "format": "json", **params})
        r.raise_for_status()
        return r.json()

    def fetch_by_ids(self, object_ids: list[str]) -> list[RawWork]:
        """``object_ids`` are exact file titles; authored order is preserved."""
        data = self._get({
            "titles": "|".join(object_ids),
            "prop": "imageinfo", "iiprop": "url|extmetadata|mime",
            "iiurlwidth": _WIDTH,
        })
        q = data.get("query") or {}
        # The API normalizes requested titles (e.g. underscores → spaces);
        # follow that mapping so output order matches the authored order.
        normalized = {n["from"]: n["to"] for n in q.get("normalized", [])}
        by_title = {p.get("title"): p for p in q.get("pages", {}).values()}
        out: list[RawWork] = []
        for t in object_ids:
            page = by_title.get(normalized.get(t, t))
            if page is None or "missing" in page:
                logger.warning("wikimedia: file %s not found", t)
                continue
            w = _to_work(page)
            if w is not None:
                out.append(w)
        return out

    def search_works(self, query: str, limit: int, artist: str | None = None) -> list[RawWork]:
        # Full-text file search; keep public-domain image files whose
        # title/artist credit contains the artist needle (defaults to the
        # query's last token, the surname).
        data = self._get({
            "generator": "search", "gsrsearch": query, "gsrnamespace": 6,
            "gsrlimit": min(50, max(limit * 4, limit)),
            "prop": "imageinfo", "iiprop": "url|extmetadata|mime",
            "iiurlwidth": _WIDTH,
        })
        pages = (data.get("query") or {}).get("pages", {})
        needle = (artist or (query.split()[-1] if query.split() else query)).lower()
        out: list[RawWork] = []
        for page in sorted(pages.values(), key=lambda p: p.get("index", 999)):
            ii = (page.get("imageinfo") or [{}])[0]
            extmeta = ii.get("extmetadata") or {}
            hay = (page.get("title", "") + " "
                   + (extmeta.get("Artist", {}).get("value") or "")).lower()
            if needle not in hay:
                continue
            w = _to_work(page)
            if w is not None and w.is_public_domain and w.has_image:
                out.append(w)
            if len(out) >= limit:
                break
        return out


def _to_work(page: dict) -> RawWork | None:
    ii = (page.get("imageinfo") or [{}])[0]
    if not ii or "image" not in (ii.get("mime") or ""):
        return None
    extmeta = ii.get("extmetadata") or {}
    url = ii.get("thumburl") or ii.get("url")
    return RawWork(
        source="wikimedia",
        source_object_id=str(page.get("pageid", "")),
        title=_title_of(page, extmeta),
        year=_year_of(extmeta),
        medium=None,
        image_url=url,
        thumb_url=url,
        source_url=ii.get("descriptionurl") or ii.get("url") or "",
        credit="Wikimedia Commons · Public domain",
        is_public_domain=_is_pd(extmeta),
        is_highlight=False,
    )
