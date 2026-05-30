"""Compute diff vs existing rows and write only what changed.

The "did anything change?" question explicitly ignores bookkeeping
timestamps and warning bags — `crawled_at`, `updated_at`,
`first_seen_at`, `_warnings`. The normalize layer stamps fresh
`crawled_at` / `updated_at` on every fetch, so a naive `merged ==
current` comparison would mark every row as updated every run.
On a 600-row sheet across 13 sources, that was costing ~600
batch_update writes per cron — purely to refresh timestamps for rows
whose actual exhibition facts had not changed.

When a patch is actually needed (real fields differ), we still
preserve `crawled_at` / `first_seen_at` from the existing row so the
"when did we first see this" semantics survive across runs.
"""

from __future__ import annotations

from dataclasses import dataclass

from crawler.sinks.base import Repository, SheetName

# Fields excluded from the diff that decides "should we patch this row?".
# These are crawl-time bookkeeping, not facts about the exhibition / venue.
_VOLATILE_FOR_DIFF: frozenset[str] = frozenset({
    "crawled_at",
    "updated_at",
    "first_seen_at",
    "_warnings",
})

# Fields whose value on the EXISTING row must survive even when a real
# patch happens — "first seen" / "first crawled" must not jump forward
# every time we re-fetch an exhibition whose title got tweaked.
_PRESERVE_FROM_EXISTING: frozenset[str] = frozenset({
    "crawled_at",
    "first_seen_at",
})


@dataclass(frozen=True)
class UpsertReport:
    new: int
    updated: int
    unchanged: int


class UpsertEngine:
    def __init__(self, repo: Repository) -> None:
        self._repo = repo

    def upsert(self, sheet: SheetName, rows: list[dict]) -> UpsertReport:
        # Some sheets accumulate blank or partial rows over time (manual edits,
        # interrupted writes). Drop anything without an id rather than crashing
        # the entire crawl on KeyError.
        existing = {
            r["id"]: r
            for r in self._repo.read_rows(sheet)
            if r.get("id")
        }
        new_rows: list[dict] = []
        patches: list[dict] = []
        unchanged = 0

        for incoming in _dedupe_by_id(rows):
            row_id = incoming["id"]
            current = existing.get(row_id)
            if current is None:
                new_rows.append(incoming)
                continue
            merged = {**current, **incoming}
            if _stable(merged) == _stable(current):
                unchanged += 1
                continue
            # Real change: carry forward the existing row's "first
            # seen" markers so they don't reset on every fetch.
            for k in _PRESERVE_FROM_EXISTING:
                existing_value = current.get(k)
                if existing_value:
                    merged[k] = existing_value
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


def _dedupe_by_id(rows: list[dict]) -> list[dict]:
    """Collapse rows sharing an id within a single batch, last occurrence
    winning. Without this, a source that emits the same exhibition N times in
    one crawl would append N identical rows (the existing-row snapshot can't
    see siblings added earlier in the same batch). Rows without an id pass
    through untouched."""
    by_id: dict[str, dict] = {}
    out: list[dict] = []
    for row in rows:
        row_id = row.get("id")
        if not row_id:
            out.append(row)
            continue
        if row_id in by_id:
            by_id[row_id].clear()
            by_id[row_id].update(row)
        else:
            slot = dict(row)
            by_id[row_id] = slot
            out.append(slot)
    return out


def _stable(row: dict) -> dict:
    """Strip volatile bookkeeping fields so two rows can be compared on
    their *content*, not on the moment they happened to be observed."""
    return {k: v for k, v in row.items() if k not in _VOLATILE_FOR_DIFF}
