"""Repository interface and shared sheet identifiers."""

from __future__ import annotations

from enum import StrEnum
from typing import Protocol


class SheetName(StrEnum):
    EXHIBITIONS = "Exhibitions"
    ARTISTS = "Artists"
    VENUES = "Venues"
    ORGANIZERS = "Organizers"
    OVERRIDES = "_overrides"


class Repository(Protocol):
    def read_rows(self, sheet: SheetName) -> list[dict]: ...
    def append_rows(self, sheet: SheetName, rows: list[dict]) -> None: ...
    def patch_rows(self, sheet: SheetName, rows: list[dict]) -> None: ...
