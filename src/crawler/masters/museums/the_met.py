"""The Metropolitan Museum of Art Open Access (CC0) client. Free, no API key."""

from __future__ import annotations

import logging

import httpx
from tenacity import retry, stop_after_attempt, wait_exponential

from crawler.masters.models import RawWork

logger = logging.getLogger(__name__)

_BASE = "https://collectionapi.metmuseum.org/public/collection/v1"


class MetClient:
    source = "the_met"

    def __init__(self, client: httpx.Client | None = None) -> None:
        self._client = client or httpx.Client(timeout=30.0)

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(max=10), reraise=True)
    def _get(self, url: str, params: dict | None = None) -> dict:
        r = self._client.get(url, params=params)
        r.raise_for_status()
        return r.json()

    def _object_data(self, object_id: str) -> dict | None:
        try:
            return self._get(f"{_BASE}/objects/{object_id}")
        except httpx.HTTPStatusError:
            logger.warning("the_met: object %s fetch failed", object_id)
            return None

    def fetch_by_ids(self, object_ids: list[str]) -> list[RawWork]:
        out: list[RawWork] = []
        for oid in object_ids:
            data = self._object_data(oid)
            if data is not None:
                out.append(_to_work(data))
        return out

    def search_works(self, query: str, limit: int) -> list[RawWork]:
        # The Met has no artist-scoped search that works for these names
        # (artistOrCulture=true returns 0), so we use a broad full-text search
        # with hasImages and filter the returned objects to this artist's
        # public-domain, image-bearing works. The last token of the query (the
        # surname) must appear in artistDisplayName.
        data = self._get(f"{_BASE}/search", params={"q": query, "hasImages": "true"})
        ids = data.get("objectIDs") or []
        needle = query.split()[-1].lower() if query.split() else query.lower()
        works: list[RawWork] = []
        # Cap the walk so a broad query can't fan out into hundreds of requests.
        for oid in ids[: max(limit * 6, limit)]:
            obj = self._object_data(str(oid))
            if obj is None:
                continue
            if needle not in (obj.get("artistDisplayName") or "").lower():
                continue
            w = _to_work(obj)
            if w.is_public_domain and w.has_image:
                works.append(w)
            if len(works) >= limit:
                break
        return works


def _to_work(data: dict) -> RawWork:
    return RawWork(
        source="the_met",
        source_object_id=str(data.get("objectID", "")),
        title=data.get("title") or "Untitled",
        year=(data.get("objectDate") or None),
        medium=(data.get("medium") or None),
        image_url=(data.get("primaryImage") or None),
        thumb_url=(data.get("primaryImageSmall") or data.get("primaryImage") or None),
        source_url=data.get("objectURL") or "",
        credit=data.get("creditLine") or "The Metropolitan Museum of Art",
        is_public_domain=bool(data.get("isPublicDomain")),
        is_highlight=bool(data.get("isHighlight")),
    )
