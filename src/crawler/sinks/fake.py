"""In-memory Repository for unit and integration tests."""

from __future__ import annotations

from crawler.sinks.base import Repository, SheetName


class FakeRepository(Repository):
    def __init__(self) -> None:
        self._data: dict[SheetName, list[dict]] = {s: [] for s in SheetName}

    def read_rows(self, sheet: SheetName) -> list[dict]:
        return [dict(row) for row in self._data[sheet]]

    def append_rows(self, sheet: SheetName, rows: list[dict]) -> None:
        self._data[sheet].extend(dict(r) for r in rows)

    def patch_rows(self, sheet: SheetName, rows: list[dict]) -> None:
        by_id = {r["id"]: r for r in self._data[sheet]}
        for patch in rows:
            row_id = patch["id"]
            if row_id not in by_id:
                raise KeyError(f"unknown id {row_id} in {sheet.value}")
            by_id[row_id].update(patch)
