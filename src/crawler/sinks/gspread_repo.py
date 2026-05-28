"""Google Sheets backend via gspread + service account.

Real-world rows are kept as dicts keyed by header. We avoid per-cell calls;
reads pull the whole sheet, writes use batch operations.
"""

from __future__ import annotations

import json
import os

import gspread
from google.oauth2.service_account import Credentials

from crawler.sinks.base import SheetName

_SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]


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
            return self._book.worksheet(sheet.value)
        except gspread.WorksheetNotFound:
            return self._book.add_worksheet(title=sheet.value, rows=1000, cols=40)

    def write_headers(self, sheet: SheetName, headers: list[str]) -> None:
        ws = self._ws(sheet)
        existing = ws.row_values(1)
        if existing == headers:
            self._cache_headers[sheet] = list(headers)
            return
        if existing and existing != headers:
            raise RuntimeError(
                f"sheet {sheet.value} has mismatched headers (got {existing}, expected {headers}); "
                "refusing to overwrite to protect data"
            )
        ws.update("A1", [headers])
        self._cache_headers[sheet] = list(headers)

    def _headers(self, sheet: SheetName) -> list[str]:
        if sheet in self._cache_headers:
            return self._cache_headers[sheet]
        headers = self._ws(sheet).row_values(1)
        self._cache_headers[sheet] = headers
        return headers

    def read_rows(self, sheet: SheetName) -> list[dict]:
        ws = self._ws(sheet)
        records = ws.get_all_records()
        return [dict(r) for r in records]

    def append_rows(self, sheet: SheetName, rows: list[dict]) -> None:
        if not rows:
            return
        ws = self._ws(sheet)
        headers = self._headers(sheet)
        values = [_serialize_row(headers, r) for r in rows]
        ws.append_rows(values, value_input_option="RAW")

    def patch_rows(self, sheet: SheetName, rows: list[dict]) -> None:
        if not rows:
            return
        ws = self._ws(sheet)
        headers = self._headers(sheet)
        existing = ws.get_all_values()
        # row 1 is headers; find id column index
        id_col = headers.index("id")
        row_index_by_id = {
            row[id_col]: i + 2  # +2: 1-based, skip header row
            for i, row in enumerate(existing[1:])
            if len(row) > id_col
        }
        updates: list[dict] = []
        for r in rows:
            row_id = r["id"]
            row_num = row_index_by_id.get(row_id)
            if row_num is None:
                raise KeyError(f"unknown id {row_id} in {sheet.value}")
            updates.append({
                "range": f"A{row_num}:{_col_letter(len(headers))}{row_num}",
                "values": [_serialize_row(headers, r)],
            })
        ws.batch_update(updates, value_input_option="RAW")


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
