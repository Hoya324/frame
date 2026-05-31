"""Idempotent worksheet + header initialization.

The repo passed in must implement `write_headers(sheet, headers)` in addition to
the read/append/patch Repository protocol. Production code uses `GspreadRepository`.
"""

from __future__ import annotations

from typing import Protocol

from crawler.sinks.base import Repository, SheetName


class HeaderRepository(Repository, Protocol):
    def write_headers(self, sheet: SheetName, headers: list[str]) -> None: ...


HEADERS: dict[SheetName, list[str]] = {
    SheetName.EXHIBITIONS: [
        "id", "source", "status", "source_url", "title", "title_en",
        "description", "poster_image_url", "medium", "exhibition_type",
        "genre_tags", "fee_type", "price_min", "price_max", "activities",
        "start_date", "end_date", "open_hours", "artist_ids", "venue_id",
        "organizer_id", "popularity_score", "featured", "crawled_at",
        "updated_at", "_warnings",
        # Added 2026-05-28 (price breakdown PR). Kept at the end so
        # existing sheets can be migrated by appending — see
        # GspreadRepository.write_headers prefix-append logic.
        "price_breakdown", "price_notes",
        # Added 2026-05-31 (translation backfill). Kept last so existing
        # sheets get these via prefix-append migration, not a mismatch error.
        "lang", "tr",
    ],
    SheetName.ARTISTS: [
        "id", "name", "name_en", "name_normalized", "bio", "instagram",
        "website", "sources", "first_seen_at", "updated_at",
        # Added 2026-05-31 (translation backfill). Kept last so existing
        # sheets get these via prefix-append migration, not a mismatch error.
        "lang", "tr",
    ],
    SheetName.VENUES: [
        "id", "name", "name_en", "venue_type", "region", "district",
        "address", "latitude", "longitude", "website", "open_hours_default",
        "sources", "first_seen_at", "updated_at",
        # Added 2026-05-28 (japan expansion). Existing sheets get this
        # appended via _plan_header_write's prefix-append branch.
        "country",
        # Added 2026-05-31 (translation backfill). Kept last so existing
        # sheets get these via prefix-append migration, not a mismatch error.
        "lang", "tr",
    ],
    SheetName.ORGANIZERS: [
        "id", "name", "name_en", "name_normalized", "organizer_type",
        "website", "sources", "first_seen_at", "updated_at",
    ],
    SheetName.OVERRIDES: [
        "entity_type", "match_pattern", "canonical_id", "note",
    ],
}


def init_sheets(repo: HeaderRepository) -> None:
    """Create or verify headers for every sheet. Idempotent."""
    for sheet, headers in HEADERS.items():
        repo.write_headers(sheet, headers)
