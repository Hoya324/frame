"""Google Sheets backend via gspread + service account.

Real-world rows are kept as dicts keyed by header. We avoid per-cell calls;
reads pull the whole sheet, writes use batch operations.

Every gspread call funnels through :func:`_api_call`, which retries on
HTTP 429 (per-minute read quota) and 503 (transient upstream) with
exponential backoff. Once the source count grew past ~6, back-to-back
``run-all`` invocations would burst past the default 60 reads/min/user
quota and lose entire sources to ``APIError [429]``; the retry plus the
``run-all`` status-recompute deduplication in :mod:`crawler.pipeline`
together absorb that burst.
"""

from __future__ import annotations

import json
import logging
import os
from collections.abc import Callable

import gspread
from google.oauth2.service_account import Credentials
from tenacity import (
    retry,
    retry_if_exception,
    stop_after_attempt,
    wait_exponential,
)

from crawler.sinks.base import SheetName

_SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]

log = logging.getLogger(__name__)

def _is_retryable_api_error(exc: BaseException) -> bool:
    """True for gspread APIErrors carrying 429 (quota) or 503 (transient)."""
    if not isinstance(exc, gspread.exceptions.APIError):
        return False
    response = getattr(exc, "response", None)
    code = getattr(response, "status_code", None)
    return code in (429, 503)


_retry_quota = retry(
    retry=retry_if_exception(_is_retryable_api_error),
    wait=wait_exponential(multiplier=2, min=2, max=64),
    stop=stop_after_attempt(6),
    reraise=True,
)


def _api_call[T](fn: Callable[[], T]) -> T:
    """Invoke a gspread call with 429/503 retry + exponential backoff."""
    return _retry_quota(fn)()


class GspreadRepository:
    def __init__(self, sheet_id: str, service_account_json: str) -> None:
        info = json.loads(service_account_json)
        creds = Credentials.from_service_account_info(info, scopes=_SCOPES)
        self._client = gspread.authorize(creds)
        self._book = self._client.open_by_key(sheet_id)
        self._cache_headers: dict[SheetName, list[str]] = {}

    @classmethod
    def from_env(cls) -> GspreadRepository:
        sheet_id = os.environ["SHEET_ID"]
        sa_json = os.environ["GOOGLE_SERVICE_ACCOUNT_JSON"]
        return cls(sheet_id, sa_json)

    def _ws(self, sheet: SheetName) -> gspread.Worksheet:
        try:
            return _api_call(lambda: self._book.worksheet(sheet.value))
        except gspread.WorksheetNotFound:
            return _api_call(
                lambda: self._book.add_worksheet(title=sheet.value, rows=1000, cols=40)
            )

    def write_headers(self, sheet: SheetName, headers: list[str]) -> None:
        ws = self._ws(sheet)
        existing = _api_call(lambda: ws.row_values(1))
        action, payload = _plan_header_write(existing, headers)
        if action == "noop":
            self._cache_headers[sheet] = list(headers)
            return
        if action == "error":
            raise RuntimeError(
                f"sheet {sheet.value} has mismatched headers (got {existing}, "
                f"expected {headers}); refusing to overwrite to protect data"
            )
        if action == "append":
            start_col = _col_letter(len(existing) + 1)
            _api_call(lambda: ws.update(f"{start_col}1", [payload]))
        else:  # action == "overwrite"
            _api_call(lambda: ws.update("A1", [headers]))
        self._cache_headers[sheet] = list(headers)

    def _headers(self, sheet: SheetName) -> list[str]:
        if sheet in self._cache_headers:
            return self._cache_headers[sheet]
        ws = self._ws(sheet)
        headers = _api_call(lambda: ws.row_values(1))
        self._cache_headers[sheet] = headers
        return headers

    def read_rows(self, sheet: SheetName) -> list[dict]:
        ws = self._ws(sheet)
        records = _api_call(lambda: ws.get_all_records())
        return [dict(r) for r in records]

    def append_rows(self, sheet: SheetName, rows: list[dict]) -> None:
        if not rows:
            return
        ws = self._ws(sheet)
        headers = self._headers(sheet)
        values = [_serialize_row(headers, r) for r in rows]
        _api_call(lambda: ws.append_rows(values, value_input_option="RAW"))

    def patch_rows(self, sheet: SheetName, rows: list[dict]) -> None:
        """Update existing rows in-place by `id`.

        Behaves as a true partial patch: the incoming dict only needs to carry
        the fields you want to change. Any unmentioned column is preserved
        from the current sheet value. (Earlier versions reused
        `_serialize_row`, which filled missing keys with empty strings and so
        wiped out untouched columns — e.g. backfill-geocodes nuking
        `first_seen_at` / `name` while patching coords.)
        """
        if not rows:
            return
        ws = self._ws(sheet)
        headers = self._headers(sheet)
        existing = _api_call(lambda: ws.get_all_values())
        id_col = headers.index("id")
        row_index_by_id: dict[str, int] = {}
        existing_by_id: dict[str, list[str]] = {}
        for i, row in enumerate(existing[1:]):
            if len(row) <= id_col:
                continue
            rid = row[id_col]
            if not rid:
                continue
            row_index_by_id[rid] = i + 2  # 1-based, skip header
            existing_by_id[rid] = row

        updates: list[dict] = []
        for r in rows:
            row_id = r["id"]
            row_num = row_index_by_id.get(row_id)
            if row_num is None:
                raise KeyError(f"unknown id {row_id} in {sheet.value}")
            current = existing_by_id[row_id]
            # Pad current to header length so a short sheet row doesn't trim
            # the merged output.
            if len(current) < len(headers):
                current = current + [""] * (len(headers) - len(current))
            merged_values = []
            for idx, h in enumerate(headers):
                if h in r:
                    v = r[h]
                    merged_values.append("" if v is None else _stringify(v))
                else:
                    merged_values.append(current[idx])
            updates.append({
                "range": f"A{row_num}:{_col_letter(len(headers))}{row_num}",
                "values": [merged_values],
            })
        _api_call(lambda: ws.batch_update(updates, value_input_option="RAW"))


def _plan_header_write(
    existing: list[str], expected: list[str]
) -> tuple[str, list[str]]:
    """Decide how to reconcile a sheet's live header row with the expected one.

    Returns ``(action, payload)`` where action is one of:
      - 'noop'      → live row already matches; payload is unused
      - 'overwrite' → sheet was empty; payload is unused (caller writes full row)
      - 'append'    → existing is a strict prefix of expected; payload is the
                      list of new column labels to append at the end
      - 'error'     → headers are incompatible (reordered / renamed / shrunk);
                      caller raises RuntimeError to protect data
    """
    if existing == expected:
        return "noop", []
    if not existing:
        return "overwrite", []
    if expected[: len(existing)] == existing and len(expected) > len(existing):
        return "append", expected[len(existing):]
    return "error", []


def _serialize_row(headers: list[str], row: dict) -> list:
    return ["" if (v := row.get(h)) is None else _stringify(v) for h in headers]


def _stringify(v) -> str:
    if isinstance(v, list):
        return ",".join(str(x) for x in v)
    if isinstance(v, bool):
        return "TRUE" if v else "FALSE"
    return str(v)


def _col_letter(n: int) -> str:
    """1 -> A, 26 -> Z, 27 -> AA."""
    out = ""
    while n > 0:
        n, rem = divmod(n - 1, 26)
        out = chr(65 + rem) + out
    return out
