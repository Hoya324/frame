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


# --- header-migration planner (used by GspreadRepository.write_headers) ---


def test_plan_header_noop_when_identical():
    from crawler.sinks.gspread_repo import _plan_header_write
    action, payload = _plan_header_write(["a", "b"], ["a", "b"])
    assert action == "noop"
    assert payload == []


def test_plan_header_overwrite_when_sheet_empty():
    from crawler.sinks.gspread_repo import _plan_header_write
    action, payload = _plan_header_write([], ["a", "b"])
    assert action == "overwrite"


def test_plan_header_appends_new_columns_when_existing_is_prefix():
    """Regression target: adding price_breakdown / price_notes at the end of
    EXHIBITIONS must auto-migrate live sheets, not crash with 'mismatched'."""
    from crawler.sinks.gspread_repo import _plan_header_write
    existing = ["id", "name", "price_min"]
    expected = ["id", "name", "price_min", "price_breakdown", "price_notes"]
    action, payload = _plan_header_write(existing, expected)
    assert action == "append"
    assert payload == ["price_breakdown", "price_notes"]


def test_plan_header_error_when_columns_reordered_or_renamed():
    from crawler.sinks.gspread_repo import _plan_header_write
    # Reordered → unsafe
    action, _ = _plan_header_write(["b", "a"], ["a", "b"])
    assert action == "error"
    # Renamed → unsafe
    action, _ = _plan_header_write(["id", "old"], ["id", "new"])
    assert action == "error"
    # Shrunk → unsafe (we don't drop user data)
    action, _ = _plan_header_write(["a", "b", "c"], ["a", "b"])
    assert action == "error"
