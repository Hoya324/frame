"""Full-reset flow — clear every sheet's data rows then restore headers."""

from __future__ import annotations

from crawler.sinks.base import SheetName
from crawler.sinks.fake import FakeRepository
from crawler.sinks.init_sheets import HEADERS
from crawler.sinks.reset import reset_sheets


class _ResetRepo(FakeRepository):
    """Fake that records header writes so we can assert headers are restored."""

    def __init__(self) -> None:
        super().__init__()
        self.headers: dict[SheetName, list[str]] = {}

    def write_headers(self, sheet: SheetName, headers: list[str]) -> None:
        self.headers[sheet] = list(headers)


def test_reset_clears_all_data_rows():
    repo = _ResetRepo()
    repo.append_rows(SheetName.EXHIBITIONS, [{"id": "e1"}, {"id": "e2"}])
    repo.append_rows(SheetName.VENUES, [{"id": "v1"}])
    repo.append_rows(SheetName.ARTISTS, [{"id": "a1"}])

    reset_sheets(repo)

    for sheet in SheetName:
        assert repo.read_rows(sheet) == []


def test_reset_restores_headers_for_every_sheet():
    repo = _ResetRepo()
    reset_sheets(repo)
    assert set(repo.headers) == set(SheetName)
    for sheet, headers in repo.headers.items():
        assert headers == HEADERS[sheet]


def test_reset_clears_then_writes_headers_so_a_fresh_crawl_starts_empty():
    repo = _ResetRepo()
    repo.append_rows(SheetName.EXHIBITIONS, [{"id": "stale"}])
    reset_sheets(repo)
    assert repo.read_rows(SheetName.EXHIBITIONS) == []
    assert repo.headers[SheetName.EXHIBITIONS] == HEADERS[SheetName.EXHIBITIONS]
