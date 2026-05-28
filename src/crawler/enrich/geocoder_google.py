"""Google Maps Geocoding API geocoder.

Returns (lat, lng) on OK, (None, None) on anything else (ZERO_RESULTS,
OVER_QUERY_LIMIT, REQUEST_DENIED, INVALID_REQUEST, UNKNOWN_ERROR).

Tenacity retry covers transient httpx errors only — quota signals come
back as HTTP 200 with `status` in the JSON body, which we treat as
"no match" rather than retrying, since retrying inside the source loop
would just burn quota faster.
"""

from __future__ import annotations

import os

import httpx
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

_URL = "https://maps.googleapis.com/maps/api/geocode/json"


class GoogleMapsGeocoder:
    def __init__(self, api_key: str, timeout: float = 10.0) -> None:
        self._key = api_key
        self._client = httpx.Client(timeout=timeout)

    @classmethod
    def from_env(cls) -> GoogleMapsGeocoder:
        return cls(api_key=os.environ["GOOGLE_MAPS_API_KEY"])

    @retry(
        retry=retry_if_exception_type(httpx.TransportError),
        wait=wait_exponential(multiplier=1, min=1, max=16),
        stop=stop_after_attempt(3),
        reraise=True,
    )
    def _get(self, params: dict) -> dict:
        r = self._client.get(_URL, params=params)
        r.raise_for_status()
        return r.json()

    def geocode(
        self, query: str, country: str = "KR"  # noqa: ARG002
    ) -> tuple[float | None, float | None]:
        if not query or not query.strip():
            return None, None
        data = self._get({
            "address": query,
            "key": self._key,
            "region": "jp",
            "language": "ja",
        })
        if data.get("status") != "OK":
            return None, None
        results = data.get("results") or []
        if not results:
            return None, None
        loc = results[0]["geometry"]["location"]
        return float(loc["lat"]), float(loc["lng"])

    def close(self) -> None:
        self._client.close()
