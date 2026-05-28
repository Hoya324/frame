"""Backfill latitude/longitude for venues that have empty coordinates."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Protocol

from crawler.sinks.base import Repository, SheetName

logger = logging.getLogger(__name__)


class GeocoderProto(Protocol):
    def geocode(
        self, query: str, country: str = "KR"
    ) -> tuple[float | None, float | None]: ...


@dataclass(frozen=True)
class BackfillReport:
    total_venues: int
    needed_geocoding: int
    geocoded: int
    no_match: int
    errors: int


def backfill_geocodes(repo: Repository, geocoder: GeocoderProto) -> BackfillReport:
    """Read all venues, geocode those missing lat/lng, and patch in one batch.

    Only venues where latitude OR longitude is blank/missing are processed.
    All successful patches are sent in a single ``repo.patch_rows()`` call.
    """
    venues = repo.read_rows(SheetName.VENUES)

    needs = [
        v
        for v in venues
        if not str(v.get("latitude") or "").strip()
        or not str(v.get("longitude") or "").strip()
    ]

    geocoded_patches: list[dict] = []
    no_match = 0
    errors = 0

    for v in needs:
        query = str(v.get("address") or v.get("name") or "").strip()
        venue_id = v.get("id", "<unknown>")

        if not query:
            logger.info("venue %s: no query string — skipping (no_match)", venue_id)
            no_match += 1
            continue

        country = str(v.get("country") or "KR").strip() or "KR"

        try:
            lat, lng = geocoder.geocode(query, country=country)
        except Exception:
            logger.exception("venue %s: geocoder raised an error", venue_id)
            errors += 1
            continue

        if lat is None or lng is None:
            logger.info("venue %s: no geocode match for %r", venue_id, query)
            no_match += 1
            continue

        logger.info("venue %s: geocoded %r → (%s, %s)", venue_id, query, lat, lng)
        geocoded_patches.append({"id": venue_id, "latitude": lat, "longitude": lng})

    if geocoded_patches:
        repo.patch_rows(SheetName.VENUES, geocoded_patches)

    report = BackfillReport(
        total_venues=len(venues),
        needed_geocoding=len(needs),
        geocoded=len(geocoded_patches),
        no_match=no_match,
        errors=errors,
    )
    logger.info(
        "backfill complete: total=%d needed=%d geocoded=%d no_match=%d errors=%d",
        report.total_venues,
        report.needed_geocoding,
        report.geocoded,
        report.no_match,
        report.errors,
    )
    return report
