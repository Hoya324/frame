"""Resolve raw artist/venue/organizer names to existing IDs or stage new entities."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime

from crawler.models import (
    Artist,
    NormalizedExhibition,
    Organizer,
    OrganizerType,
    Venue,
    VenueType,
)
from crawler.normalize.categories import map_organizer_type, map_venue_type
from crawler.normalize.dedup import artist_id, organizer_id, venue_id
from crawler.normalize.text import normalize_name


@dataclass
class EntityState:
    artists: list[Artist]
    venues: list[Venue]
    organizers: list[Organizer]
    overrides: list[dict]


@dataclass
class ResolveResult:
    exhibition: NormalizedExhibition
    new_artists: list[Artist] = field(default_factory=list)
    new_venues: list[Venue] = field(default_factory=list)
    new_organizers: list[Organizer] = field(default_factory=list)


def _override_lookup(overrides: list[dict], entity_type: str) -> dict[str, str]:
    """match_pattern -> canonical_id."""
    return {
        o["match_pattern"]: o["canonical_id"]
        for o in overrides
        if o.get("entity_type") == entity_type and o.get("match_pattern") and o.get("canonical_id")
    }


def resolve_entities(
    exh: NormalizedExhibition,
    state: EntityState,
) -> ResolveResult:
    now = datetime.now(UTC)
    source = exh.source.value

    # --- Artists (N:M) ---
    artist_overrides = _override_lookup(state.overrides, "artist")
    artists_by_id = {a.id: a for a in state.artists}
    artists_by_norm = {a.name_normalized: a for a in state.artists}

    resolved_artist_ids: list[str] = []
    new_artists: list[Artist] = []
    for raw_name in exh.artist_raw_names:
        if raw_name in artist_overrides:
            target = artist_overrides[raw_name]
            if target in artists_by_id:
                resolved_artist_ids.append(target)
                continue
        norm = normalize_name(raw_name)
        if not norm:
            continue
        if norm in artists_by_norm:
            resolved_artist_ids.append(artists_by_norm[norm].id)
            continue
        new_id = artist_id(norm)
        new_artists.append(
            Artist(
                id=new_id,
                name=raw_name,
                name_normalized=norm,
                sources=[source],
                first_seen_at=now,
                updated_at=now,
            )
        )
        artists_by_norm[norm] = new_artists[-1]
        resolved_artist_ids.append(new_id)

    # --- Venue (N:1) ---
    venue_overrides = _override_lookup(state.overrides, "venue")
    new_venues: list[Venue] = []
    resolved_venue_id = ""
    if exh.venue_raw_name:
        if exh.venue_raw_name in venue_overrides:
            resolved_venue_id = venue_overrides[exh.venue_raw_name]
        else:
            # NormalizedExhibition only carries the venue name at this stage;
            # actual address is resolved later inside the Venue entity.
            candidate_id = venue_id(exh.venue_raw_name, None)
            existing = next((v for v in state.venues if v.id == candidate_id), None)
            if existing:
                resolved_venue_id = existing.id
            else:
                new_venues.append(
                    Venue(
                        id=candidate_id,
                        name=exh.venue_raw_name,
                        venue_type=map_venue_type(exh.venue_raw_name) or VenueType.OTHER,
                        region=exh.venue_raw_region,
                        address=exh.venue_raw_address,
                        sources=[source],
                        first_seen_at=now,
                        updated_at=now,
                    )
                )
                resolved_venue_id = candidate_id

    # --- Organizer (N:1) ---
    organizer_overrides = _override_lookup(state.overrides, "organizer")
    new_organizers: list[Organizer] = []
    resolved_organizer_id = resolved_venue_id  # fallback: same as venue
    if exh.organizer_raw_name:
        if exh.organizer_raw_name in organizer_overrides:
            resolved_organizer_id = organizer_overrides[exh.organizer_raw_name]
        else:
            norm = normalize_name(exh.organizer_raw_name)
            existing = next(
                (o for o in state.organizers if o.name_normalized == norm),
                None,
            )
            if existing:
                resolved_organizer_id = existing.id
            else:
                new_id = organizer_id(norm)
                new_organizers.append(
                    Organizer(
                        id=new_id,
                        name=exh.organizer_raw_name,
                        name_normalized=norm,
                        organizer_type=(
                            map_organizer_type(exh.organizer_raw_name)
                            or OrganizerType.OTHER
                        ),
                        sources=[source],
                        first_seen_at=now,
                        updated_at=now,
                    )
                )
                resolved_organizer_id = new_id

    resolved = exh.model_copy(update={
        "artist_ids": resolved_artist_ids,
        "venue_id": resolved_venue_id,
        "organizer_id": resolved_organizer_id,
    })

    return ResolveResult(
        exhibition=resolved,
        new_artists=new_artists,
        new_venues=new_venues,
        new_organizers=new_organizers,
    )
