"""Kakao Local API geocoder. Address search first, keyword fallback."""

from __future__ import annotations

import os

import httpx
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

_ADDRESS_URL = "https://dapi.kakao.com/v2/local/search/address.json"
_KEYWORD_URL = "https://dapi.kakao.com/v2/local/search/keyword.json"


class KakaoGeocoder:
    def __init__(self, api_key: str, timeout: float = 10.0) -> None:
        self._client = httpx.Client(
            timeout=timeout,
            headers={"Authorization": f"KakaoAK {api_key}"},
        )

    @classmethod
    def from_env(cls) -> KakaoGeocoder:
        return cls(api_key=os.environ["KAKAO_REST_API_KEY"])

    @retry(
        retry=retry_if_exception_type(httpx.TransportError),
        wait=wait_exponential(multiplier=1, min=1, max=16),
        stop=stop_after_attempt(3),
        reraise=True,
    )
    def _get(self, url: str, params: dict) -> dict:
        r = self._client.get(url, params=params)
        r.raise_for_status()
        return r.json()

    def geocode(self, query: str) -> tuple[float | None, float | None]:
        if not query:
            return None, None
        # Try address search first
        data = self._get(_ADDRESS_URL, {"query": query})
        docs = data.get("documents", [])
        if docs:
            d = docs[0]
            return float(d["y"]), float(d["x"])
        # Fallback to keyword search (place name)
        data = self._get(_KEYWORD_URL, {"query": query})
        docs = data.get("documents", [])
        if docs:
            d = docs[0]
            return float(d["y"]), float(d["x"])
        return None, None

    def close(self) -> None:
        self._client.close()
