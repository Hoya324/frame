"""End-to-end orchestration for a single source."""

from __future__ import annotations

import logging
import time
from collections.abc import Iterable
from datetime import date
from typing import Protocol

from crawler.models import (
    Artist,
    NormalizedExhibition,
    Organizer,
    RawExhibition,
    SourceName,
    Venue,
)
from crawler.normalize import normalize_exhibition
from crawler.normalize.status import compute_status
from crawler.reporter import SourceReport
from crawler.resolver.entities import EntityState, resolve_entities
from crawler.sinks.base import Repository, SheetName
from crawler.sinks.upsert import UpsertEngine

log = logging.getLogger(__name__)


class Extractor(Protocol):
    name: SourceName

    def crawl(self) -> Iterable[RawExhibition]: ...


class GeocoderProto(Protocol):
    def geocode(self, query: str) -> tuple[float | None, float | None]: ...


def _exhibition_row(e: NormalizedExhibition) -> dict:
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


def run_source(
    extractor: Extractor,
    repo: Repository,
    geocoder: GeocoderProto,
    today: date,
) -> SourceReport:
    name = extractor.name.value
    started = time.monotonic()

    state = EntityState(
        artists=[_artist_from_row(r) for r in repo.read_rows(SheetName.ARTISTS)],
        venues=[_venue_from_row(r) for r in repo.read_rows(SheetName.VENUES)],
        organizers=[_organizer_from_row(r) for r in repo.read_rows(SheetName.ORGANIZERS)],
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

                # geocode brand-new venues
                for v in result.new_venues:
                    lat, lng = geocoder.geocode(v.address or v.name)
                    if lat is not None and lng is not None:
                        v.latitude, v.longitude = lat, lng
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


def _artist_from_row(r: dict) -> Artist:
    from datetime import datetime
    return Artist(
        id=r["id"],
        name=r["name"],
        name_en=r.get("name_en") or None,
        name_normalized=r["name_normalized"],
        bio=r.get("bio") or None,
        instagram=r.get("instagram") or None,
        website=r.get("website") or None,
        sources=[s for s in (r.get("sources") or "").split(",") if s],
        first_seen_at=datetime.fromisoformat(r["first_seen_at"]),
        updated_at=datetime.fromisoformat(r["updated_at"]),
    )


def _venue_from_row(r: dict) -> Venue:
    from datetime import datetime

    from crawler.models import VenueType
    return Venue(
        id=r["id"],
        name=r["name"],
        name_en=r.get("name_en") or None,
        venue_type=VenueType(r.get("venue_type") or "other"),
        region=r.get("region") or None,
        district=r.get("district") or None,
        address=r.get("address") or None,
        latitude=float(r["latitude"]) if r.get("latitude") not in (None, "") else None,
        longitude=float(r["longitude"]) if r.get("longitude") not in (None, "") else None,
        website=r.get("website") or None,
        open_hours_default=r.get("open_hours_default") or None,
        sources=[s for s in (r.get("sources") or "").split(",") if s],
        first_seen_at=datetime.fromisoformat(r["first_seen_at"]),
        updated_at=datetime.fromisoformat(r["updated_at"]),
    )


def _organizer_from_row(r: dict) -> Organizer:
    from datetime import datetime

    from crawler.models import OrganizerType
    return Organizer(
        id=r["id"],
        name=r["name"],
        name_en=r.get("name_en") or None,
        name_normalized=r["name_normalized"],
        organizer_type=OrganizerType(r.get("organizer_type") or "other"),
        website=r.get("website") or None,
        sources=[s for s in (r.get("sources") or "").split(",") if s],
        first_seen_at=datetime.fromisoformat(r["first_seen_at"]),
        updated_at=datetime.fromisoformat(r["updated_at"]),
    )
