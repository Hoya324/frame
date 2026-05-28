from crawler.sinks.base import SheetName
from crawler.sinks.fake import FakeRepository
from crawler.sinks.init_sheets import HEADERS, init_sheets


class _RecordingRepo(FakeRepository):
    """Fake that tracks header writes for the init flow."""

    def __init__(self) -> None:
        super().__init__()
        self.headers: dict[SheetName, list[str]] = {}

    def write_headers(self, sheet: SheetName, headers: list[str]) -> None:
        self.headers[sheet] = list(headers)


def test_init_sheets_writes_all_five_headers():
    repo = _RecordingRepo()
    init_sheets(repo)
    assert set(repo.headers) == set(SheetName)
    for sheet, headers in repo.headers.items():
        assert headers == HEADERS[sheet]


def test_init_sheets_is_idempotent_on_matching_headers():
    repo = _RecordingRepo()
    init_sheets(repo)
    init_sheets(repo)  # second call should not raise
    assert set(repo.headers) == set(SheetName)
