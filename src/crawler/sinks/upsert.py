"""Compute diff vs existing rows and write only what changed."""

from __future__ import annotations

from dataclasses import dataclass

from crawler.sinks.base import Repository, SheetName


@dataclass(frozen=True)
class UpsertReport:
    new: int
    updated: int
    unchanged: int


class UpsertEngine:
    def __init__(self, repo: Repository) -> None:
        self._repo = repo

    def upsert(self, sheet: SheetName, rows: list[dict]) -> UpsertReport:
        existing = {r["id"]: r for r in self._repo.read_rows(sheet)}
        new_rows: list[dict] = []
        patches: list[dict] = []
        unchanged = 0

        for incoming in rows:
            row_id = incoming["id"]
            current = existing.get(row_id)
            if current is None:
                new_rows.append(incoming)
                continue
            merged = {**current, **incoming}
            if merged == current:
                unchanged += 1
            else:
                patches.append(merged)

        if new_rows:
            self._repo.append_rows(sheet, new_rows)
        if patches:
            self._repo.patch_rows(sheet, patches)

        return UpsertReport(
            new=len(new_rows),
            updated=len(patches),
            unchanged=unchanged,
        )
