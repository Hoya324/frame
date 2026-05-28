"""Per-country geocoder dispatch.

Keeps a country → backend table. Unknown countries fall back to the
KR backend (Kakao); a (None, None) outcome there is just "no match" and
the pipeline handles that case by saving the venue without coordinates.
"""

from __future__ import annotations

from typing import Protocol


class _GeocoderBackend(Protocol):
    def geocode(self, query: str) -> tuple[float | None, float | None]: ...


class GeocoderResolver:
    def __init__(self, kakao: _GeocoderBackend, google: _GeocoderBackend) -> None:
        self._kakao = kakao
        self._google = google
        self._by_country: dict[str, _GeocoderBackend] = {
            "KR": kakao,
            "JP": google,
        }

    def geocode(
        self,
        query: str,
        country: str = "KR",
    ) -> tuple[float | None, float | None]:
        backend = self._by_country.get(country, self._kakao)
        return backend.geocode(query)

    def close(self) -> None:
        # Both backends expose .close(); guard for fakes in tests.
        for backend in (self._kakao, self._google):
            close = getattr(backend, "close", None)
            if callable(close):
                close()
