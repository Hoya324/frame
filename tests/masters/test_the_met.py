import json
from pathlib import Path

import httpx
import respx

from crawler.masters.museums.the_met import MetClient

FIX = Path(__file__).parent.parent / "fixtures" / "masters"


def _obj():
    return json.loads((FIX / "met_object_269434.json").read_text())


@respx.mock
def test_fetch_by_ids_maps_public_domain_object():
    respx.get(
        "https://collectionapi.metmuseum.org/public/collection/v1/objects/269434"
    ).mock(return_value=httpx.Response(200, json=_obj()))

    client = MetClient()
    works = client.fetch_by_ids(["269434"])

    assert len(works) == 1
    w = works[0]
    assert w.source == "the_met"
    assert w.source_object_id == "269434"
    assert w.is_public_domain is True
    assert w.image_url  # primaryImage
    assert w.source_url.startswith("https://www.metmuseum.org/")
    assert w.work_id == "the_met-269434"


@respx.mock
def test_search_filters_to_artist_pd_with_image():
    # Broad full-text search returns the object id; the client keeps it only
    # because the artist name matches the query.
    respx.get(
        "https://collectionapi.metmuseum.org/public/collection/v1/search"
    ).mock(return_value=httpx.Response(200, json={"total": 1, "objectIDs": [269434]}))
    respx.get(
        "https://collectionapi.metmuseum.org/public/collection/v1/objects/269434"
    ).mock(return_value=httpx.Response(200, json=_obj()))

    works = MetClient().search_works("Julia Margaret Cameron", limit=5)
    assert [w.source_object_id for w in works] == ["269434"]


@respx.mock
def test_search_drops_objects_by_other_artists():
    # Same object (Cameron) but a query for a different artist → filtered out.
    respx.get(
        "https://collectionapi.metmuseum.org/public/collection/v1/search"
    ).mock(return_value=httpx.Response(200, json={"total": 1, "objectIDs": [269434]}))
    respx.get(
        "https://collectionapi.metmuseum.org/public/collection/v1/objects/269434"
    ).mock(return_value=httpx.Response(200, json=_obj()))
    assert MetClient().search_works("Walker Evans", limit=5) == []


@respx.mock
def test_search_handles_null_objectids():
    respx.get(
        "https://collectionapi.metmuseum.org/public/collection/v1/search"
    ).mock(return_value=httpx.Response(200, json={"total": 0, "objectIDs": None}))
    assert MetClient().search_works("Nobody", limit=5) == []
