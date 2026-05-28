from collections.abc import Iterable
from datetime import date

from freezegun import freeze_time

from crawler.models import (
    RawExhibition,
    SourceName,
    Status,
)
from crawler.pipeline import run_source
from crawler.reporter import SourceReport
from crawler.sinks.base import SheetName
from crawler.sinks.fake import FakeRepository
from crawler.sinks.init_sheets import init_sheets


class _DummyExtractor:
    name = SourceName.ARTMAP

    def __init__(self, raws: list[RawExhibition]) -> None:
        self.raws = raws

    def crawl(self) -> Iterable[RawExhibition]:
        yield from self.raws


class _FakeHeaderRepo(FakeRepository):
    def write_headers(self, sheet: SheetName, headers: list[str]) -> None:  # noqa: ARG002
        return None  # not needed for in-memory


class _NullGeocoder:
    def geocode(self, query: str) -> tuple[float | None, float | None]:  # noqa: ARG002
        return None, None


def _raw(idx: int, title: str) -> RawExhibition:
    return RawExhibition(
        source=SourceName.ARTMAP,
        source_url=f"https://art-map.co.kr/exhibition/view.php?idx={idx}",
        raw={
            "title": title,
            "venue_name": "류가헌",
            "artists": ["김작가"],
            "date_range": "2026.06.01 ~ 2026.07.01",
            "fee_text": "무료",
            "exhibition_type_text": "개인전",
        },
    )


@freeze_time("2026-05-28")
def test_run_source_end_to_end():
    repo = _FakeHeaderRepo()
    init_sheets(repo)
    extractor = _DummyExtractor([_raw(1, "A"), _raw(2, "B")])

    report: SourceReport = run_source(
        extractor=extractor,
        repo=repo,
        geocoder=_NullGeocoder(),
        today=date(2026, 5, 28),
    )

    assert report.name == "artmap"
    assert report.extracted == 2
    assert report.new == 2  # both new
    exh_rows = repo.read_rows(SheetName.EXHIBITIONS)
    assert {r["title"] for r in exh_rows} == {"A", "B"}
    # status was computed
    for r in exh_rows:
        assert r["status"] == Status.UPCOMING.value
    # one venue created and reused (artist too)
    assert len(repo.read_rows(SheetName.VENUES)) == 1
    assert len(repo.read_rows(SheetName.ARTISTS)) == 1


@freeze_time("2026-05-28")
def test_run_source_isolates_item_failure():
    repo = _FakeHeaderRepo()
    init_sheets(repo)
    # second item is missing title → normalize raises → item skipped
    bad = RawExhibition(
        source=SourceName.ARTMAP,
        source_url="https://art-map.co.kr/exhibition/view.php?idx=99",
        raw={"venue_name": "류가헌"},
    )
    extractor = _DummyExtractor([_raw(1, "A"), bad, _raw(2, "B")])

    report = run_source(
        extractor=extractor,
        repo=repo,
        geocoder=_NullGeocoder(),
        today=date(2026, 5, 28),
    )

    assert report.extracted == 3
    assert report.new == 2
    assert report.errors == 1
    assert report.failure is None  # not promoted to source failure
