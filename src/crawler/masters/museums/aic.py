"""Art Institute of Chicago Open Access (CC0) client. Free, no API key.
A descriptive User-Agent is requested by AIC's API guidelines."""

from __future__ import annotations

import logging

import httpx
from tenacity import retry, stop_after_attempt, wait_exponential

from crawler.masters.models import RawWork

logger = logging.getLogger(__name__)

_BASE = "https://api.artic.edu/api/v1/artworks"
_IIIF = "https://www.artic.edu/iiif/2"
_FIELDS = "id,title,date_display,medium_display,image_id,is_public_domain,artist_title"
_UA = "frame-photo (hoyana1225@gmail.com)"


class AicClient:
    source = "aic"

    def __init__(self, client: httpx.Client | None = None) -> None:
        self._client = client or httpx.Client(timeout=30.0, headers={"AIC-User-Agent": _UA})

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(max=10), reraise=True)
    def _get(self, url: str, params: dict | None = None) -> dict:
        r = self._client.get(url, params=params)
        r.raise_for_status()
        return r.json()

    def search_works(self, query: str, limit: int) -> list[RawWork]:
        # AIC search `q` is broad full-text; request extra results and keep only
        # this artist's public-domain, image-bearing works (surname must appear
        # in artist_title), then cap at `limit`.
        data = self._get(
            f"{_BASE}/search",
            params={"q": query, "fields": _FIELDS, "limit": max(limit * 3, limit)},
        )
        needle = query.split()[-1].lower() if query.split() else query.lower()
        out: list[RawWork] = []
        for rec in data.get("data") or []:
            if needle not in (rec.get("artist_title") or "").lower():
                continue
            w = _to_work(rec)
            if w is not None and w.is_public_domain and w.has_image:
                out.append(w)
            if len(out) >= limit:
                break
        return out

    def fetch_by_ids(self, object_ids: list[str]) -> list[RawWork]:
        out: list[RawWork] = []
        for oid in object_ids:
            try:
                data = self._get(f"{_BASE}/{oid}", params={"fields": _FIELDS})
            except httpx.HTTPStatusError:
                logger.warning("aic: object %s fetch failed", oid)
                continue
            w = _to_work(data.get("data") or {})
            if w is not None:
                out.append(w)
        return out


def _to_work(rec: dict) -> RawWork | None:
    oid = rec.get("id")
    if oid is None:
        return None
    image_id = rec.get("image_id")
    image_url = f"{_IIIF}/{image_id}/full/843,/0/default.jpg" if image_id else None
    thumb_url = f"{_IIIF}/{image_id}/full/200,/0/default.jpg" if image_id else None
    return RawWork(
        source="aic",
        source_object_id=str(oid),
        title=rec.get("title") or "Untitled",
        year=(rec.get("date_display") or None),
        medium=(rec.get("medium_display") or None),
        image_url=image_url,
        thumb_url=thumb_url,
        source_url=f"https://www.artic.edu/artworks/{oid}",
        credit="Art Institute of Chicago · CC0",
        is_public_domain=bool(rec.get("is_public_domain")),
        is_highlight=False,
    )
