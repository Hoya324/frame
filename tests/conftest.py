"""Shared pytest configuration and fixtures."""

from __future__ import annotations

import pytest

from crawler.sinks.base import SheetName
from crawler.sinks.fake import FakeRepository
from crawler.sinks.init_sheets import init_sheets


class FakeHeaderRepo(FakeRepository):
    """FakeRepository extended with a no-op write_headers (not needed for in-memory)."""

    def write_headers(self, sheet: SheetName, headers: list[str]) -> None:  # noqa: ARG002
        return None


class NullGeocoder:
    """Geocoder stub that always returns (None, None) — no network calls."""

    def geocode(self, query: str) -> tuple[float | None, float | None]:  # noqa: ARG002
        return None, None


@pytest.fixture()
def header_repo() -> FakeHeaderRepo:
    """Return a fresh, sheet-initialised FakeHeaderRepo."""
    repo = FakeHeaderRepo()
    init_sheets(repo)
    return repo


@pytest.fixture()
def null_geocoder() -> NullGeocoder:
    """Return a fresh NullGeocoder instance."""
    return NullGeocoder()
