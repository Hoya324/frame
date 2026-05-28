"""Integration test: Artmap end-to-end pipeline with fake sink.

Mocks the POST endpoint at https://art-map.co.kr/data/new_exhibition.php
using the real fixture HTML (4 cards). Verifies that data flows through
normalize → resolve → upsert into the FakeRepository correctly.
"""

from datetime import date
from pathlib import Path

import httpx
import respx
from freezegun import freeze_time

from crawler.models import SourceName
from crawler.pipeline import run_source
from crawler.sinks.base import SheetName
from crawler.sinks.fake import FakeRepository
from crawler.sinks.init_sheets import init_sheets
from crawler.sources.artmap import ArtmapExtractor


FIXTURE = Path(__file__).parent.parent / "fixtures" / "artmap" / "list_page_1.html"


class _FakeHeaderRepo(FakeRepository):
    def write_headers(self, sheet: SheetName, headers: list[str]) -> None:  # noqa: ARG002
        return None


class _NullGeocoder:
    def geocode(self, query: str) -> tuple[float | None, float | None]:  # noqa: ARG002
        return None, None


@respx.mock
@freeze_time("2026-05-28")
def test_artmap_end_to_end_writes_to_fake_sheet():
    list_html = FIXTURE.read_text(encoding="utf-8")
    # ArtmapExtractor uses POST to /data/new_exhibition.php (not GET to new_list.php)
    respx.post("https://art-map.co.kr/data/new_exhibition.php").mock(
        return_value=httpx.Response(200, text=list_html)
    )

    repo = _FakeHeaderRepo()
    init_sheets(repo)

    report = run_source(
        extractor=ArtmapExtractor(max_batches=1, delay_s=0.0),
        repo=repo,
        geocoder=_NullGeocoder(),
        today=date(2026, 5, 28),
    )

    assert report.failure is None
    assert report.errors == 0
    assert report.extracted >= 1
    assert report.new >= 1

    exh = repo.read_rows(SheetName.EXHIBITIONS)
    assert len(exh) == report.extracted
    # every row has id, title, status set
    for r in exh:
        assert r["id"] and r["title"] and r["status"]

    venues = repo.read_rows(SheetName.VENUES)
    assert len(venues) >= 1
    # all exhibition rows point to existing venue ids
    venue_ids = {v["id"] for v in venues}
    for r in exh:
        assert r["venue_id"] in venue_ids
