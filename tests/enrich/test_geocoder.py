import httpx
import respx

from crawler.enrich.geocoder import KakaoGeocoder


@respx.mock
def test_geocoder_returns_lat_lng_on_match():
    respx.get("https://dapi.kakao.com/v2/local/search/address.json").mock(
        return_value=httpx.Response(200, json={
            "documents": [{
                "y": "37.582",
                "x": "126.969",
                "address_name": "서울 종로구 자하문로 106",
            }],
        })
    )
    geo = KakaoGeocoder(api_key="test")
    lat, lng = geo.geocode("서울 종로구 자하문로 106")
    assert lat == 37.582 and lng == 126.969


@respx.mock
def test_geocoder_returns_none_when_no_match():
    respx.get("https://dapi.kakao.com/v2/local/search/address.json").mock(
        return_value=httpx.Response(200, json={"documents": []})
    )
    respx.get("https://dapi.kakao.com/v2/local/search/keyword.json").mock(
        return_value=httpx.Response(200, json={"documents": []})
    )
    geo = KakaoGeocoder(api_key="test")
    assert geo.geocode("nowhere") == (None, None)


@respx.mock
def test_geocoder_falls_back_to_keyword_search_on_address_miss():
    respx.get("https://dapi.kakao.com/v2/local/search/address.json").mock(
        return_value=httpx.Response(200, json={"documents": []})
    )
    respx.get("https://dapi.kakao.com/v2/local/search/keyword.json").mock(
        return_value=httpx.Response(200, json={
            "documents": [{"y": "37.5", "x": "127.0"}],
        })
    )
    geo = KakaoGeocoder(api_key="test")
    assert geo.geocode("류가헌") == (37.5, 127.0)
