from pathlib import Path

import httpx
import respx

from crawler.models import SourceName
from crawler.sources.pgi import PgiExtractor, _parse_detail, _parse_list

FIXTURE_DIR = Path(__file__).parent.parent / "fixtures" / "pgi"


def _list_html() -> str:
    return (FIXTURE_DIR / "list.html").read_text(encoding="utf-8")


def _detail_html() -> str:
    return (FIXTURE_DIR / "detail_11241.html").read_text(encoding="utf-8")


def test_parse_list_extracts_each_exhibition():
    items = _parse_list(_list_html())
    by_url = {it["source_url"]: it for it in items}

    top = by_url["https://www.pgi.ac/exhibitions/11241"]
    assert top["title"] == "原直久 「柘榴」"
    assert top["date_range"] == "2026.05.22~2026.07.11"


def test_parse_list_title_keeps_trailing_year_in_name():
    # "PARIS PHOTO 2025 2025.11.13(木) － 11.16(日)": the in-name year stays,
    # only the leading date token is stripped.
    items = _parse_list(_list_html())
    by_url = {it["source_url"]: it for it in items}
    paris = by_url["https://www.pgi.ac/exhibitions/11029"]
    assert paris["title"] == "PARIS PHOTO 2025"
    assert paris["date_range"] == "2025.11.13~2025.11.16"


def test_parse_list_dedupes_and_finds_all():
    items = _parse_list(_list_html())
    urls = [it["source_url"] for it in items]
    assert len(urls) == len(set(urls))
    assert len(items) == 7


def test_parse_detail_pulls_poster_and_description():
    d = _parse_detail(_detail_html())
    assert d["poster_image_url"] == (
        "https://www.pgi.ac/pgi/wp-content/uploads/2026/04/"
        "Hara_8-0191-800-apr3-2026_2500.jpg"
    )
    # Description is the body prose, free of the ©caption and bare date rows.
    assert d["description"].startswith("日本大学名誉教授の原直久先生が")
    assert "©" not in d["description"]


@respx.mock
def test_crawl_yields_normalized_raws():
    respx.get("https://www.pgi.ac/exhibitions").mock(
        return_value=httpx.Response(200, text=_list_html())
    )
    respx.route(
        method="GET",
        url__regex=r"pgi\.ac/exhibitions/\d+",
    ).mock(return_value=httpx.Response(200, text=_detail_html()))

    raws = list(PgiExtractor(delay_s=0.0).crawl())

    assert len(raws) == 7
    assert all(r.source is SourceName.PGI for r in raws)
    by_url = {str(r.source_url): r for r in raws}
    top = by_url["https://www.pgi.ac/exhibitions/11241"]
    assert top.raw["title"] == "原直久 「柘榴」"
    assert top.raw["date_range"] == "2026.05.22~2026.07.11"
    assert top.raw["category"] == "写真"
    assert top.raw["venue_region"] == "東京"
    assert top.raw["poster_image_url"].endswith(".jpg")
