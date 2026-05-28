"""End-to-end orchestration for a single source."""

from __future__ import annotations

import logging
import time
from collections.abc import Iterable
from datetime import date
from typing import ClassVar, Protocol

from crawler.models import (
    Artist,
    NormalizedExhibition,
    Organizer,
    RawExhibition,
    SourceName,
    Venue,
)
from crawler.normalize import normalize_exhibition
from crawler.normalize.status import compute_status, status_patches_for_all
from crawler.reporter import SourceReport
from crawler.resolver.entities import EntityState, resolve_entities
from crawler.sinks.base import Repository, SheetName
from crawler.sinks.upsert import UpsertEngine

log = logging.getLogger(__name__)


class Extractor(Protocol):
    name: SourceName
    country: ClassVar[str]

    def crawl(self) -> Iterable[RawExhibition]: ...


class GeocoderProto(Protocol):
    def geocode(self, query: str) -> tuple[float | None, float | None]: ...


def _exhibition_row(e: NormalizedExhibition) -> dict:
    import json
    return {
        "id": e.id,
        "source": e.source.value,
        "status": e.status.value,
        "source_url": str(e.source_url),
        "title": e.title,
        "title_en": e.title_en or "",
        "description": e.description or "",
        "poster_image_url": str(e.poster_image_url) if e.poster_image_url else "",
        "medium": e.medium.value,
        "exhibition_type": e.exhibition_type.value,
        "genre_tags": ",".join(e.genre_tags),
        "fee_type": e.fee_type.value,
        "price_min": e.price_min if e.price_min is not None else "",
        "price_max": e.price_max if e.price_max is not None else "",
        "activities": ",".join(e.activities),
        "start_date": e.start_date.isoformat() if e.start_date else "",
        "end_date": e.end_date.isoformat() if e.end_date else "",
        "open_hours": e.open_hours or "",
        "artist_ids": ",".join(e.artist_ids),
        "venue_id": e.venue_id,
        "organizer_id": e.organizer_id,
        "popularity_score": e.popularity_score if e.popularity_score is not None else "",
        "featured": "TRUE" if e.featured else "FALSE",
        "crawled_at": e.crawled_at.isoformat(),
        "updated_at": e.updated_at.isoformat(),
        "_warnings": ",".join(e.warnings),
        "price_breakdown": (
            json.dumps(
                [t.model_dump() for t in e.price_breakdown],
                ensure_ascii=False,
            )
            if e.price_breakdown
            else ""
        ),
        "price_notes": e.price_notes or "",
    }


def _artist_row(a: Artist) -> dict:
    return {
        "id": a.id, "name": a.name, "name_en": a.name_en or "",
        "name_normalized": a.name_normalized, "bio": a.bio or "",
        "instagram": str(a.instagram) if a.instagram else "",
        "website": str(a.website) if a.website else "",
        "sources": ",".join(a.sources),
        "first_seen_at": a.first_seen_at.isoformat(),
        "updated_at": a.updated_at.isoformat(),
    }


def _venue_row(v: Venue) -> dict:
    return {
        "id": v.id, "name": v.name, "name_en": v.name_en or "",
        "venue_type": v.venue_type.value, "region": v.region or "",
        "district": v.district or "", "address": v.address or "",
        "country": v.country,
        "latitude": v.latitude if v.latitude is not None else "",
        "longitude": v.longitude if v.longitude is not None else "",
        "website": str(v.website) if v.website else "",
        "open_hours_default": v.open_hours_default or "",
        "sources": ",".join(v.sources),
        "first_seen_at": v.first_seen_at.isoformat(),
        "updated_at": v.updated_at.isoformat(),
    }


def _organizer_row(o: Organizer) -> dict:
    return {
        "id": o.id, "name": o.name, "name_en": o.name_en or "",
        "name_normalized": o.name_normalized,
        "organizer_type": o.organizer_type.value,
        "website": str(o.website) if o.website else "",
        "sources": ",".join(o.sources),
        "first_seen_at": o.first_seen_at.isoformat(),
        "updated_at": o.updated_at.isoformat(),
    }


def recompute_stale_status(repo: Repository, today: date) -> int:
    """Re-classify status across ALL exhibitions; return the patch count.

    Spec §6.1 step 7. Exists as a standalone entry point so `run-all` can
    invoke it once after every source has finished, instead of every source
    paying the read+patch cost itself (which exhausts the Sheets API
    read-per-minute quota once the source count grows past ~6).
    """
    rows = repo.read_rows(SheetName.EXHIBITIONS)
    patches = status_patches_for_all(today, rows)
    if patches:
        repo.patch_rows(SheetName.EXHIBITIONS, patches)
    return len(patches)


def run_source(
    extractor: Extractor,
    repo: Repository,
    geocoder: GeocoderProto,
    today: date,
    recompute_status: bool = True,
) -> SourceReport:
    name = extractor.name.value
    started = time.monotonic()

    state = EntityState(
        artists=_hydrate(repo, SheetName.ARTISTS, _artist_from_row, name),
        venues=_hydrate(repo, SheetName.VENUES, _venue_from_row, name),
        organizers=_hydrate(repo, SheetName.ORGANIZERS, _organizer_from_row, name),
        overrides=repo.read_rows(SheetName.OVERRIDES),
    )

    engine = UpsertEngine(repo)

    extracted = 0
    errors = 0
    failure: str | None = None
    exh_rows: list[dict] = []
    new_artists_acc: list[Artist] = []
    new_venues_acc: list[Venue] = []
    new_organizers_acc: list[Organizer] = []

    try:
        for raw in extractor.crawl():
            extracted += 1
            try:
                normalized = normalize_exhibition(raw)
                result = resolve_entities(normalized, state)

                # geocode brand-new venues; geocoder failures don't drop the venue
                for v in result.new_venues:
                    try:
                        lat, lng = geocoder.geocode(v.address or v.name)
                        if lat is not None and lng is not None:
                            v.latitude, v.longitude = lat, lng
                    except Exception as geo_exc:
                        log.warning(
                            "geocode failed for venue '%s' in %s: %s; "
                            "venue saved without coordinates",
                            v.name, name, geo_exc,
                        )
                    new_venues_acc.append(v)
                    state.venues.append(v)

                for a in result.new_artists:
                    new_artists_acc.append(a)
                    state.artists.append(a)
                for o in result.new_organizers:
                    new_organizers_acc.append(o)
                    state.organizers.append(o)

                e = result.exhibition
                e = e.model_copy(update={"status": compute_status(today, e.start_date, e.end_date)})
                exh_rows.append(_exhibition_row(e))
            except Exception as exc:  # per-item isolation
                errors += 1
                log.warning("item failed in %s: %s", name, exc)
    except Exception as exc:
        failure = f"{type(exc).__name__}: {exc}"
        log.error("source %s failed: %s", name, exc)

    if new_artists_acc:
        engine.upsert(SheetName.ARTISTS, [_artist_row(a) for a in new_artists_acc])
    if new_venues_acc:
        engine.upsert(SheetName.VENUES, [_venue_row(v) for v in new_venues_acc])
    if new_organizers_acc:
        engine.upsert(SheetName.ORGANIZERS, [_organizer_row(o) for o in new_organizers_acc])

    new = updated = unchanged = 0
    if exh_rows:
        rep = engine.upsert(SheetName.EXHIBITIONS, exh_rows)
        new += rep.new
        updated += rep.updated
        unchanged += rep.unchanged

    # Spec §6.1 step 7: recompute status across ALL exhibitions rows,
    # including those not in today's batch (e.g. upcoming → past transitions).
    # run-all skips this per source and does it once at the end of the run.
    if recompute_status:
        updated += recompute_stale_status(repo, today)

    return SourceReport(
        name=name,
        extracted=extracted,
        new=new,
        updated=updated,
        unchanged=unchanged,
        errors=errors,
        duration_s=time.monotonic() - started,
        failure=failure,
    )


# --- helpers: row -> model for state hydration ---


def _hydrate(repo: Repository, sheet: SheetName, builder, source_name: str) -> list:
    """Materialize rows into entities, skipping (and logging) corrupted ones.

    Rows missing an `id`/`name` or carrying empty datetime fields would
    otherwise propagate as `ValueError: Invalid isoformat string: ''` and
    abort the entire crawl. Skipping is safer than failing the run.
    """
    out = []
    skipped = 0
    for r in repo.read_rows(sheet):
        try:
            entity = builder(r)
        except (ValueError, KeyError) as exc:
            skipped += 1
            log.warning(
                "skipping malformed row in %s during %s: id=%r err=%s",
                sheet.value, source_name, r.get("id"), exc,
            )
            continue
        if entity is None:
            skipped += 1
            log.warning(
                "skipping malformed row in %s during %s: id=%r (missing required field)",
                sheet.value, source_name, r.get("id"),
            )
            continue
        out.append(entity)
    if skipped:
        log.warning("hydrate %s for %s: skipped %d row(s)", sheet.value, source_name, skipped)
    return out


def _s(value) -> str:
    """Coerce a cell value to a stripped string.

    gspread's `get_all_records` auto-parses numeric-looking cells into int/float
    (e.g. a venue named '2025' or a numeric latitude), so the bare `.strip()`
    pattern blows up with `AttributeError`. Going through `str()` keeps the
    hydrators tolerant of whatever shape gspread hands us.
    """
    if value is None:
        return ""
    return str(value).strip()


def _opt_s(value) -> str | None:
    s = _s(value)
    return s or None


def _parse_dt(value):
    """Return a datetime parsed from an ISO string, or None for blank input."""
    from datetime import datetime
    s = _s(value)
    if not s:
        return None
    return datetime.fromisoformat(s)


def _parse_float(value):
    s = _s(value)
    if not s:
        return None
    return float(s)


def _artist_from_row(r: dict) -> Artist | None:
    row_id = _s(r.get("id"))
    name = _s(r.get("name"))
    first_seen = _parse_dt(r.get("first_seen_at"))
    updated = _parse_dt(r.get("updated_at"))
    if not row_id or not name or first_seen is None or updated is None:
        return None
    return Artist(
        id=row_id,
        name=name,
        name_en=_opt_s(r.get("name_en")),
        name_normalized=_s(r.get("name_normalized")) or name,
        bio=_opt_s(r.get("bio")),
        instagram=_opt_s(r.get("instagram")),
        website=_opt_s(r.get("website")),
        sources=[s for s in _s(r.get("sources")).split(",") if s],
        first_seen_at=first_seen,
        updated_at=updated,
    )


def _venue_from_row(r: dict) -> Venue | None:
    from crawler.models import VenueType
    row_id = _s(r.get("id"))
    name = _s(r.get("name"))
    first_seen = _parse_dt(r.get("first_seen_at"))
    updated = _parse_dt(r.get("updated_at"))
    if not row_id or not name or first_seen is None or updated is None:
        return None
    return Venue(
        id=row_id,
        name=name,
        name_en=_opt_s(r.get("name_en")),
        venue_type=VenueType(_s(r.get("venue_type")) or "other"),
        region=_opt_s(r.get("region")),
        district=_opt_s(r.get("district")),
        address=_opt_s(r.get("address")),
        country=_s(r.get("country")) or "KR",
        latitude=_parse_float(r.get("latitude")),
        longitude=_parse_float(r.get("longitude")),
        website=_opt_s(r.get("website")),
        open_hours_default=_opt_s(r.get("open_hours_default")),
        sources=[s for s in _s(r.get("sources")).split(",") if s],
        first_seen_at=first_seen,
        updated_at=updated,
    )


def _organizer_from_row(r: dict) -> Organizer | None:
    from crawler.models import OrganizerType
    row_id = _s(r.get("id"))
    name = _s(r.get("name"))
    first_seen = _parse_dt(r.get("first_seen_at"))
    updated = _parse_dt(r.get("updated_at"))
    if not row_id or not name or first_seen is None or updated is None:
        return None
    return Organizer(
        id=row_id,
        name=name,
        name_en=_opt_s(r.get("name_en")),
        name_normalized=_s(r.get("name_normalized")) or name,
        organizer_type=OrganizerType(_s(r.get("organizer_type")) or "other"),
        website=_opt_s(r.get("website")),
        sources=[s for s in _s(r.get("sources")).split(",") if s],
        first_seen_at=first_seen,
        updated_at=updated,
    )
