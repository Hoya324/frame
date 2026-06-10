import httpx
import respx

from crawler.masters.museums.commons import CommonsClient

_API = "https://commons.wikimedia.org/w/api.php"


def _page(pageid, title, *, lic="Public domain", artist="Kusakabe Kimbei",
          mime="image/jpeg", date="circa 1890", index=1, object_name=""):
    return {
        "pageid": pageid, "title": title, "index": index,
        "imageinfo": [{
            "mime": mime,
            "url": f"https://upload.wikimedia.org/orig/{pageid}.jpg",
            "thumburl": f"https://upload.wikimedia.org/thumb/{pageid}.jpg",
            "descriptionurl": f"https://commons.wikimedia.org/wiki/{title}",
            "extmetadata": {
                "LicenseShortName": {"value": lic},
                "Artist": {"value": artist},
                "DateTimeOriginal": {"value": date},
                "ObjectName": {"value": object_name},
            },
        }],
    }


@respx.mock
def test_search_filters_to_pd_image_files_matching_artist_needle():
    pages = {
        "1": _page(1, "File:View of Yokohama.jpg", date="<p>1880s, taken 1885</p>"),
        "2": _page(2, "File:Modern scan.jpg", lic="CC BY-SA 4.0", index=2),
        "3": _page(3, "File:Other photographer.jpg", artist="Someone Else", index=3),
        "4": _page(4, "File:Some video.webm", mime="video/webm", index=4),
    }
    respx.get(_API).mock(return_value=httpx.Response(
        200, json={"query": {"pages": pages}}
    ))

    works = CommonsClient().search_works("Kusakabe Kimbei", limit=10, artist="Kimbei")

    assert [w.source_object_id for w in works] == ["1"]
    w = works[0]
    assert w.source == "wikimedia"
    assert w.work_id == "wikimedia-1"
    # The API-rendered thumburl is served as-is for both sizes.
    assert w.image_url == "https://upload.wikimedia.org/thumb/1.jpg"
    assert w.thumb_url == w.image_url
    assert w.source_url == "https://commons.wikimedia.org/wiki/File:View of Yokohama.jpg"
    assert w.title == "View of Yokohama"  # filename fallback, ext stripped
    assert w.year == "1885"  # 4-digit year mined from HTML-laden date
    assert w.is_public_domain is True


@respx.mock
def test_fetch_by_ids_preserves_authored_order_and_follows_normalization():
    resp = {"query": {
        "normalized": [{"from": "File:b_2.jpg", "to": "File:B 2.jpg"}],
        "pages": {
            "10": _page(10, "File:A 1.jpg", object_name="A nice print"),
            "20": _page(20, "File:B 2.jpg"),
            "-1": {"title": "File:Gone.jpg", "missing": ""},
        },
    }}
    respx.get(_API).mock(return_value=httpx.Response(200, json=resp))

    works = CommonsClient().fetch_by_ids(["File:b_2.jpg", "File:A 1.jpg", "File:Gone.jpg"])

    # Authored order kept (normalized title resolved), missing file skipped.
    assert [w.source_object_id for w in works] == ["20", "10"]
    assert works[1].title == "A nice print"  # ObjectName preferred over filename
