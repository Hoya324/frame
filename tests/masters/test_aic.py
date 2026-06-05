import json
from pathlib import Path

import httpx
import respx

from crawler.masters.museums.aic import AicClient

FIX = Path(__file__).parent.parent / "fixtures" / "masters"


def _search():
    return json.loads((FIX / "aic_search_stieglitz.json").read_text())


def _object():
    return json.loads((FIX / "aic_object.json").read_text())


@respx.mock
def test_search_builds_iiif_urls_and_filters_to_artist_pd_with_image():
    data = {
        "data": [
            {"id": 100, "title": "The Steerage", "date_display": "1907",
             "medium_display": "Photogravure", "image_id": "abc",
             "is_public_domain": True, "artist_title": "Alfred Stieglitz"},
            {"id": 101, "title": "No Image", "date_display": "1910",
             "medium_display": "Print", "image_id": None,
             "is_public_domain": True, "artist_title": "Alfred Stieglitz"},
            {"id": 102, "title": "In Copyright", "date_display": "1950",
             "medium_display": "Print", "image_id": "def",
             "is_public_domain": False, "artist_title": "Alfred Stieglitz"},
            {"id": 103, "title": "Other Artist", "date_display": "1907",
             "medium_display": "Print", "image_id": "ghi",
             "is_public_domain": True, "artist_title": "Someone Else"},
        ]
    }
    respx.get("https://api.artic.edu/api/v1/artworks/search").mock(
        return_value=httpx.Response(200, json=data)
    )

    works = AicClient().search_works("Alfred Stieglitz", limit=10)

    # Only PD + has image + artist surname matches the query.
    assert [w.source_object_id for w in works] == ["100"]
    w = works[0]
    assert w.source == "aic"
    assert w.image_url == "https://www.artic.edu/iiif/2/abc/full/843,/0/default.jpg"
    assert w.thumb_url == "https://www.artic.edu/iiif/2/abc/full/200,/0/default.jpg"
    assert w.source_url == "https://www.artic.edu/artworks/100"
    assert w.year == "1907"


@respx.mock
def test_fetch_by_ids_maps_object_without_artist_filter():
    obj = {"data": {"id": 100, "title": "The Steerage", "date_display": "1907",
                    "medium_display": "Photogravure", "image_id": "abc",
                    "is_public_domain": True, "artist_title": "Alfred Stieglitz"}}
    respx.get("https://api.artic.edu/api/v1/artworks/100").mock(
        return_value=httpx.Response(200, json=obj)
    )
    works = AicClient().fetch_by_ids(["100"])  # explicit ids skip the artist filter
    assert works[0].work_id == "aic-100"
    assert works[0].is_public_domain is True
