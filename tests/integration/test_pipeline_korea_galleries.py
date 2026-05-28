"""Integration smoke tests: all 7 new Korean gallery sources through the full pipeline.

Each test exercises: source.crawl() → normalize_exhibition() → resolve_entities()
→ upsert into FakeHeaderRepo.  HTTP is mocked via respx so no network traffic
occurs.  Asserts that no exception propagates and that at least one row lands in
the EXHIBITIONS sheet.
"""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path

import httpx
import respx
from freezegun import freeze_time

from crawler.pipeline import run_source
from crawler.sinks.base import SheetName
from crawler.sources.canon_gallery import _LIST_URL as CANON_LIST_URL
from crawler.sources.canon_gallery import CanonGalleryExtractor
from crawler.sources.gallery_kong import _LIST_URL as KONG_LIST_URL
from crawler.sources.gallery_kong import GalleryKongExtractor
from crawler.sources.gallery_lux import _LIST_URL as LUX_LIST_URL
from crawler.sources.gallery_lux import GalleryLuxExtractor
from crawler.sources.goeun import _LIST_URL as GOEUN_LIST_URL
from crawler.sources.goeun import GoeunExtractor
from crawler.sources.ilwoo_space import _LIST_URL as ILWOO_LIST_URL
from crawler.sources.ilwoo_space import IlwooSpaceExtractor
from crawler.sources.ryugaheon import _LIST_URL as RYUGAHEON_LIST_URL
from crawler.sources.ryugaheon import RyugaheonExtractor
from crawler.sources.sangsangmadang import _LIST_URL as SSMD_LIST_URL
from crawler.sources.sangsangmadang import SangsangmadangExtractor
from tests.conftest import FakeHeaderRepo, NullGeocoder

_FIXTURES = Path(__file__).parent.parent / "fixtures"

# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


# ---------------------------------------------------------------------------
# goeun (고은사진미술관)
# ---------------------------------------------------------------------------


@respx.mock
@freeze_time("2026-05-28")
def test_goeun_end_to_end(
    header_repo: FakeHeaderRepo,
    null_geocoder: NullGeocoder,
) -> None:
    """GET /bbs/board.php?bo_table=exhibition&page=N; stops on empty page."""
    list_html = _read(_FIXTURES / "goeun" / "list_current.html")
    empty_html = "<html><body></body></html>"

    # respx matches by URL string; goeun builds params dict so the request URL
    # includes ?bo_table=exhibition&page=1 etc.  Use a side_effect to serve
    # the real fixture for page=1 and empty HTML for everything else.
    call_count = 0

    def _side(request: httpx.Request) -> httpx.Response:
        nonlocal call_count
        call_count += 1
        page = request.url.params.get("page", "1")
        if page == "1":
            return httpx.Response(200, text=list_html)
        return httpx.Response(200, text=empty_html)

    respx.get(GOEUN_LIST_URL).mock(side_effect=_side)

    report = run_source(
        extractor=GoeunExtractor(max_pages=2, delay_s=0.0),
        repo=header_repo,
        geocoder=null_geocoder,
        today=date(2026, 5, 28),
    )

    assert report.failure is None, report.failure
    assert report.errors == 0
    assert report.extracted >= 1
    assert len(header_repo.read_rows(SheetName.EXHIBITIONS)) == report.extracted


# ---------------------------------------------------------------------------
# gallery_lux (갤러리 룩스)
# ---------------------------------------------------------------------------


@respx.mock
@freeze_time("2026-05-28")
def test_gallery_lux_end_to_end(
    header_repo: FakeHeaderRepo,
    null_geocoder: NullGeocoder,
) -> None:
    """GET /archive/ (page 1), GET /archive/page/2/ (empty → stop)."""
    list_html = _read(_FIXTURES / "gallery_lux" / "list_page_1.html")
    empty_html = "<html><body></body></html>"

    respx.get(LUX_LIST_URL).mock(return_value=httpx.Response(200, text=list_html))
    respx.get("https://gallerylux.net/archive/page/2/").mock(
        return_value=httpx.Response(200, text=empty_html)
    )

    report = run_source(
        extractor=GalleryLuxExtractor(max_pages=2, delay_s=0.0),
        repo=header_repo,
        geocoder=null_geocoder,
        today=date(2026, 5, 28),
    )

    assert report.failure is None, report.failure
    assert report.errors == 0
    assert report.extracted >= 1
    assert len(header_repo.read_rows(SheetName.EXHIBITIONS)) == report.extracted


# ---------------------------------------------------------------------------
# gallery_kong (공근혜갤러리)
# ---------------------------------------------------------------------------


@respx.mock
@freeze_time("2026-05-28")
def test_gallery_kong_end_to_end(
    header_repo: FakeHeaderRepo,
    null_geocoder: NullGeocoder,
) -> None:
    """GET list page, then GET each detail URL."""
    list_html = _read(_FIXTURES / "gallery_kong" / "list_page_1.html")
    detail_kwak = _read(_FIXTURES / "gallery_kong" / "detail_2022_KwakIntan.html")
    detail_kenna = _read(_FIXTURES / "gallery_kong" / "detail_2022_MichaelKenna.html")
    detail_jenpak = _read(_FIXTURES / "gallery_kong" / "detail_2022_jenpak.html")

    respx.get(KONG_LIST_URL).mock(return_value=httpx.Response(200, text=list_html))
    respx.get("https://www.konggallery.com/2022_KwakIntan_palette").mock(
        return_value=httpx.Response(200, text=detail_kwak)
    )
    respx.get("https://www.konggallery.com/2022__MichaelKenna").mock(
        return_value=httpx.Response(200, text=detail_kenna)
    )
    respx.get("https://www.konggallery.com/2022_jenpak_IntotheVoid").mock(
        return_value=httpx.Response(200, text=detail_jenpak)
    )

    report = run_source(
        extractor=GalleryKongExtractor(delay_s=0.0),
        repo=header_repo,
        geocoder=null_geocoder,
        today=date(2026, 5, 28),
    )

    assert report.failure is None, report.failure
    assert report.errors == 0
    assert report.extracted >= 1
    assert len(header_repo.read_rows(SheetName.EXHIBITIONS)) == report.extracted


# ---------------------------------------------------------------------------
# ryugaheon (류가헌)
# ---------------------------------------------------------------------------


@respx.mock
@freeze_time("2026-05-28")
def test_ryugaheon_end_to_end(
    header_repo: FakeHeaderRepo,
    null_geocoder: NullGeocoder,
) -> None:
    """Single GET to the Naver Blog RSS feed XML."""
    rss_xml = _read(_FIXTURES / "ryugaheon" / "list_page_1.html")

    respx.get(RYUGAHEON_LIST_URL).mock(return_value=httpx.Response(200, text=rss_xml))

    report = run_source(
        extractor=RyugaheonExtractor(delay_s=0.0),
        repo=header_repo,
        geocoder=null_geocoder,
        today=date(2026, 5, 28),
    )

    assert report.failure is None, report.failure
    assert report.errors == 0
    assert report.extracted >= 1
    assert len(header_repo.read_rows(SheetName.EXHIBITIONS)) == report.extracted


# ---------------------------------------------------------------------------
# ilwoo_space (일우스페이스)
# ---------------------------------------------------------------------------


@respx.mock
@freeze_time("2026-05-28")
def test_ilwoo_space_end_to_end(
    header_repo: FakeHeaderRepo,
    null_geocoder: NullGeocoder,
) -> None:
    """GET /default/m02/p03.php (page 1); page 2 returns empty → stop."""
    list_html = _read(_FIXTURES / "ilwoo_space" / "list_page_1.html")
    empty_html = "<html><body></body></html>"

    call_count = 0

    def _side(request: httpx.Request) -> httpx.Response:
        nonlocal call_count
        call_count += 1
        # page 1 has no query params; page 2+ has com_board_page=2
        page = request.url.params.get("com_board_page", "1")
        if page == "1":
            return httpx.Response(200, text=list_html)
        return httpx.Response(200, text=empty_html)

    respx.get(ILWOO_LIST_URL).mock(side_effect=_side)

    report = run_source(
        extractor=IlwooSpaceExtractor(max_pages=2, delay_s=0.0),
        repo=header_repo,
        geocoder=null_geocoder,
        today=date(2026, 5, 28),
    )

    assert report.failure is None, report.failure
    assert report.errors == 0
    assert report.extracted >= 1
    assert len(header_repo.read_rows(SheetName.EXHIBITIONS)) == report.extracted


# ---------------------------------------------------------------------------
# sangsangmadang (KT&G 상상마당)
# ---------------------------------------------------------------------------


@respx.mock
@freeze_time("2026-05-28")
def test_sangsangmadang_end_to_end(
    header_repo: FakeHeaderRepo,
    null_geocoder: NullGeocoder,
) -> None:
    """POST JSON API; only photo-keyword titles pass the whitelist filter."""
    list_json = _read(_FIXTURES / "sangsangmadang" / "list_all.json")
    empty_response = json.dumps({"displayListInfo": {"displayList": []}})

    call_count = 0

    def _side(request: httpx.Request) -> httpx.Response:
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            return httpx.Response(200, text=list_json)
        return httpx.Response(200, text=empty_response)

    respx.post(SSMD_LIST_URL).mock(side_effect=_side)

    report = run_source(
        extractor=SangsangmadangExtractor(max_pages=2, delay_s=0.0),
        repo=header_repo,
        geocoder=null_geocoder,
        today=date(2026, 5, 28),
    )

    assert report.failure is None, report.failure
    assert report.errors == 0
    assert report.extracted >= 1
    assert len(header_repo.read_rows(SheetName.EXHIBITIONS)) == report.extracted


# ---------------------------------------------------------------------------
# canon_gallery (캐논 갤러리)
# ---------------------------------------------------------------------------


@respx.mock
@freeze_time("2026-05-28")
def test_canon_gallery_end_to_end(
    header_repo: FakeHeaderRepo,
    null_geocoder: NullGeocoder,
) -> None:
    """POST AJAX endpoint returning HTML fragment; max_pages=1 to avoid extra calls."""
    list_html = _read(_FIXTURES / "canon_gallery" / "list_page_1.html")

    # The fixture contains `totalPageCount = 7` which would normally cause 7
    # POST calls.  Setting max_pages=1 caps iteration at one request.
    respx.post(CANON_LIST_URL).mock(return_value=httpx.Response(200, text=list_html))

    report = run_source(
        extractor=CanonGalleryExtractor(max_pages=1, delay_s=0.0),
        repo=header_repo,
        geocoder=null_geocoder,
        today=date(2026, 5, 28),
    )

    assert report.failure is None, report.failure
    assert report.errors == 0
    assert report.extracted >= 1
    assert len(header_repo.read_rows(SheetName.EXHIBITIONS)) == report.extracted
