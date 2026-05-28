"""Behavior tests for the gspread Sheets backend.

Focus: the retry-on-quota wrapper. Per-source dedup reads burst past the
default Sheets API quota of 60 reads/min/user once the source count grows
past ~6; without retry, individual sources lose their entire batch to an
unhandled APIError [429].
"""

from __future__ import annotations

from unittest.mock import MagicMock

import gspread
import pytest

from crawler.sinks.gspread_repo import (
    GspreadRepository,
    _api_call,
    _is_retryable_api_error,
)


def _api_error(status_code: int) -> gspread.exceptions.APIError:
    response = MagicMock()
    response.status_code = status_code
    response.json.return_value = {"error": {"code": status_code, "message": "x"}}
    return gspread.exceptions.APIError(response)


def test_is_retryable_api_error_matches_quota_and_unavailable():
    assert _is_retryable_api_error(_api_error(429)) is True
    assert _is_retryable_api_error(_api_error(503)) is True


def test_is_retryable_api_error_skips_other_codes():
    assert _is_retryable_api_error(_api_error(400)) is False
    assert _is_retryable_api_error(_api_error(403)) is False
    assert _is_retryable_api_error(_api_error(500)) is False
    assert _is_retryable_api_error(ValueError("nope")) is False


def test_api_call_retries_on_429_then_succeeds(monkeypatch):
    """The wrapper must eat at least one 429 before giving up."""
    # Speed up the wait_exponential schedule for tests.
    import tenacity
    monkeypatch.setattr(tenacity.wait_exponential, "__call__", lambda *a, **kw: 0)

    calls = {"n": 0}

    def flaky():
        calls["n"] += 1
        if calls["n"] < 3:
            raise _api_error(429)
        return "ok"

    assert _api_call(flaky) == "ok"
    assert calls["n"] == 3


def test_api_call_does_not_retry_on_403(monkeypatch):
    """Non-retryable APIErrors propagate immediately (no backoff loop)."""
    import tenacity
    monkeypatch.setattr(tenacity.wait_exponential, "__call__", lambda *a, **kw: 0)

    calls = {"n": 0}

    def explode():
        calls["n"] += 1
        raise _api_error(403)

    with pytest.raises(gspread.exceptions.APIError):
        _api_call(explode)
    assert calls["n"] == 1


class _FakeWorksheet:
    def __init__(self, records: list[dict], fail_429_times: int = 0):
        self._records = records
        self._fail_remaining = fail_429_times
        self.append_calls: list[list[list[str]]] = []
        self.batch_update_calls: list[list[dict]] = []

    def get_all_records(self):
        if self._fail_remaining > 0:
            self._fail_remaining -= 1
            raise _api_error(429)
        return list(self._records)

    def get_all_values(self):
        return [["id"]] + [[r["id"]] for r in self._records]

    def row_values(self, n):
        return ["id"]

    def append_rows(self, values, value_input_option=None):
        self.append_calls.append(values)

    def batch_update(self, updates, value_input_option=None):
        self.batch_update_calls.append(updates)


class _FakeSpreadsheet:
    def __init__(self, ws: _FakeWorksheet):
        self._ws = ws

    def worksheet(self, name):
        return self._ws


def _build_repo(ws: _FakeWorksheet) -> GspreadRepository:
    repo = GspreadRepository.__new__(GspreadRepository)
    repo._client = MagicMock()
    repo._book = _FakeSpreadsheet(ws)
    repo._cache_headers = {}
    return repo


def test_read_rows_survives_transient_quota(monkeypatch):
    """A single 429 on get_all_records is retried, not propagated."""
    import tenacity
    monkeypatch.setattr(tenacity.wait_exponential, "__call__", lambda *a, **kw: 0)

    ws = _FakeWorksheet(records=[{"id": "a"}, {"id": "b"}], fail_429_times=1)
    from crawler.sinks.base import SheetName
    repo = _build_repo(ws)
    rows = repo.read_rows(SheetName.EXHIBITIONS)
    assert [r["id"] for r in rows] == ["a", "b"]
