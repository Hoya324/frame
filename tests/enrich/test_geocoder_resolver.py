"""GeocoderResolver dispatches geocode(query, country) to the right backend."""

from __future__ import annotations

from crawler.enrich.geocoder_resolver import GeocoderResolver


class _FakeGeocoder:
    def __init__(self, lat: float, lng: float):
        self._lat, self._lng = lat, lng
        self.calls: list[str] = []

    def geocode(self, query: str) -> tuple[float | None, float | None]:
        self.calls.append(query)
        return self._lat, self._lng


def test_resolver_routes_KR_to_kakao():
    kakao = _FakeGeocoder(37.5, 127.0)
    google = _FakeGeocoder(35.6, 139.7)
    r = GeocoderResolver(kakao=kakao, google=google)

    assert r.geocode("서울특별시 종로구", country="KR") == (37.5, 127.0)
    assert kakao.calls == ["서울특별시 종로구"]
    assert google.calls == []


def test_resolver_routes_JP_to_google():
    kakao = _FakeGeocoder(37.5, 127.0)
    google = _FakeGeocoder(35.6, 139.7)
    r = GeocoderResolver(kakao=kakao, google=google)

    assert r.geocode("東京都目黒区", country="JP") == (35.6, 139.7)
    assert google.calls == ["東京都目黒区"]
    assert kakao.calls == []


def test_resolver_defaults_unspecified_country_to_KR():
    """Backward compat: legacy callers without country land on Kakao."""
    kakao = _FakeGeocoder(37.5, 127.0)
    google = _FakeGeocoder(35.6, 139.7)
    r = GeocoderResolver(kakao=kakao, google=google)

    assert r.geocode("서울특별시 종로구") == (37.5, 127.0)
    assert kakao.calls == ["서울특별시 종로구"]


def test_resolver_unknown_country_falls_back_to_KR_geocoder():
    """An unrecognized country (e.g. 'TW' before TW geocoder ships) still
    geocodes via the default, with a no-match outcome being normal."""
    kakao = _FakeGeocoder(37.5, 127.0)
    google = _FakeGeocoder(35.6, 139.7)
    r = GeocoderResolver(kakao=kakao, google=google)

    lat, lng = r.geocode("台北市", country="TW")
    assert (lat, lng) == (37.5, 127.0)  # routed to kakao default
    assert kakao.calls == ["台北市"]
