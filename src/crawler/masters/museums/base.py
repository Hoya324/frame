"""Common interface every museum client implements."""

from __future__ import annotations

from typing import Protocol

from crawler.masters.models import RawWork


class MuseumClient(Protocol):
    source: str

    def fetch_by_ids(self, object_ids: list[str]) -> list[RawWork]:
        """Fetch specific objects by their museum ids, preserving order."""
        ...

    def search_works(self, query: str, limit: int) -> list[RawWork]:
        """Search by artist/name and return up to ``limit`` candidate works."""
        ...
