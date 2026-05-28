"""GoogleMapsGeocoder unit tests via respx mock of the HTTPS endpoint."""

from __future__ import annotations

import httpx
import pytest
import respx

from crawler.enrich.geocoder_google import GoogleMapsGeocoder

_URL = "https://maps.googleapis.com/maps/api/geocode/json"


@respx.mock
def test_geocode_returns_lat_lng_on_ok():
    respx.get(_URL).mock(
        return_value=httpx.Response(
            200,
            json={
                "status": "OK",
                "results": [
                    {"geometry": {"location": {"lat": 35.6438, "lng": 139.7138}}}
                ],
            },
        )
    )
    g = GoogleMapsGeocoder(api_key="fake-key")
    lat, lng = g.geocode("東京都目黒区三田1-13-3")
    assert lat == pytest.approx(35.6438)
    assert lng == pytest.approx(139.7138)


@respx.mock
def test_geocode_returns_none_none_on_zero_results():
    respx.get(_URL).mock(
        return_value=httpx.Response(
            200, json={"status": "ZERO_RESULTS", "results": []}
        )
    )
    g = GoogleMapsGeocoder(api_key="fake-key")
    assert g.geocode("nonsense address") == (None, None)


@respx.mock
def test_geocode_returns_none_none_on_quota_exhausted():
    respx.get(_URL).mock(
        return_value=httpx.Response(
            200,
            json={
                "status": "OVER_QUERY_LIMIT",
                "results": [],
                "error_message": "...",
            },
        )
    )
    g = GoogleMapsGeocoder(api_key="fake-key")
    assert g.geocode("any query") == (None, None)


def test_geocode_returns_none_none_on_empty_query():
    g = GoogleMapsGeocoder(api_key="fake-key")
    assert g.geocode("") == (None, None)
    assert g.geocode("   ") == (None, None)


@respx.mock
def test_geocode_sends_region_and_language_params():
    route = respx.get(_URL).mock(
        return_value=httpx.Response(
            200, json={"status": "ZERO_RESULTS", "results": []}
        )
    )
    g = GoogleMapsGeocoder(api_key="fake-key")
    g.geocode("六本木")
    sent = route.calls.last.request
    assert "region=jp" in str(sent.url)
    assert "language=ja" in str(sent.url)
    assert "address=" in str(sent.url)
    assert "key=fake-key" in str(sent.url)
