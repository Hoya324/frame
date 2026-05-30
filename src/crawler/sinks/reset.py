"""DESTRUCTIVE full reset: clear every sheet's rows, then restore headers.

The crawler only ever upserts (append + patch-by-id), so stale rows — dropped
sources, non-photo carryover, duplicate or bad-coordinate venues — accumulate
forever. A clean re-crawl needs the canonical store emptied first; that is what
this does. Headers are rewritten immediately so the next crawl can serialize.
"""

from __future__ import annotations

from typing import Protocol

from crawler.sinks.base import SheetName
from crawler.sinks.init_sheets import HeaderRepository, init_sheets


class ResetRepository(HeaderRepository, Protocol):
    def clear_sheet(self, sheet: SheetName) -> None: ...


def reset_sheets(repo: ResetRepository) -> None:
    """Empty every worksheet then re-write its header row."""
    for sheet in SheetName:
        repo.clear_sheet(sheet)
    init_sheets(repo)
