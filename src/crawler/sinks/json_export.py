"""Export the canonical store to a denormalized JSON snapshot for the web frontend."""

from __future__ import annotations

import json
import math
import os
from datetime import UTC, datetime

from crawler.sinks.base import Repository, SheetName


def _id(value: object) -> str:
    """Stable string id. Coercing guards against upstream numeric corruption
    (e.g. an all-digit id read back as a float) producing a non-string key."""
    return str(value)


def _split(value: object) -> list[str]:
    if not value:
        return []
    return [part.strip() for part in str(value).split(",") if part.strip()]


def _str_or_none(value: object) -> str | None:
    if value is None:
        return None
    text = str(value)
    return text if text != "" else None


def _int_or_none(value: object) -> int | None:
    if value is None or value == "":
        return None
    return int(value)


def _float_or_none(value: object) -> float | None:
    if value is None or value == "":
        return None
    f = float(value)
    # Drop NaN/Infinity — they are not representable in standard JSON and would
    # break strict parsers (e.g. the web app's bundler).
    return f if math.isfinite(f) else None


def _bool(value: object) -> bool:
    if isinstance(value, bool):
        return value
    return str(value).strip().upper() == "TRUE"


def _venue_full(row: dict) -> dict:
    return {
        "id": _id(row["id"]),
        "name": row.get("name", ""),
        "name_en": _str_or_none(row.get("name_en")),
        "venue_type": _str_or_none(row.get("venue_type")),
        "region": _str_or_none(row.get("region")),
        "district": _str_or_none(row.get("district")),
        "address": _str_or_none(row.get("address")),
        "country": _str_or_none(row.get("country")),
        "lat": _float_or_none(row.get("latitude")),
        "lng": _float_or_none(row.get("longitude")),
        "website": _str_or_none(row.get("website")),
    }


def _venue_embed(row: dict) -> dict:
    return {
        "id": _id(row["id"]),
        "name": row.get("name", ""),
        "region": _str_or_none(row.get("region")),
        "district": _str_or_none(row.get("district")),
        "lat": _float_or_none(row.get("latitude")),
        "lng": _float_or_none(row.get("longitude")),
    }


def _artist_full(row: dict) -> dict:
    return {
        "id": _id(row["id"]),
        "name": row.get("name", ""),
        "name_en": _str_or_none(row.get("name_en")),
    }


def _exhibition_json(row: dict, venues: dict[str, dict], artists: dict[str, dict]) -> dict:
    venue_id = _str_or_none(row.get("venue_id"))
    venue_row = venues.get(venue_id) if venue_id else None
    artist_ids = _split(row.get("artist_ids"))
    return {
        "id": _id(row["id"]),
        "title": row.get("title", ""),
        "title_en": _str_or_none(row.get("title_en")),
        "poster_image_url": _str_or_none(row.get("poster_image_url")),
        "description": _str_or_none(row.get("description")),
        "medium": _str_or_none(row.get("medium")),
        "exhibition_type": _str_or_none(row.get("exhibition_type")),
        "genre_tags": _split(row.get("genre_tags")),
        "fee_type": _str_or_none(row.get("fee_type")),
        "price_min": _int_or_none(row.get("price_min")),
        "price_max": _int_or_none(row.get("price_max")),
        "start_date": _str_or_none(row.get("start_date")),
        "end_date": _str_or_none(row.get("end_date")),
        "status": _str_or_none(row.get("status")),
        "open_hours": _str_or_none(row.get("open_hours")),
        "venue": _venue_embed(venue_row) if venue_row else None,
        "artists": [
            {"id": _id(artists[aid]["id"]), "name": artists[aid]["name"]}
            for aid in artist_ids
            if aid in artists
        ],
        "source_url": _str_or_none(row.get("source_url")),
        "featured": _bool(row.get("featured")),
        "popularity_score": _float_or_none(row.get("popularity_score")),
    }


def build_catalog(repo: Repository, generated_at: datetime) -> dict:
    venue_rows = repo.read_rows(SheetName.VENUES)
    artist_rows = repo.read_rows(SheetName.ARTISTS)
    exhibition_rows = repo.read_rows(SheetName.EXHIBITIONS)

    venues_by_id = {r["id"]: r for r in venue_rows}
    artists_by_id = {r["id"]: r for r in artist_rows}

    return {
        "generated_at": generated_at.isoformat(),
        "exhibitions": [
            _exhibition_json(r, venues_by_id, artists_by_id) for r in exhibition_rows
        ],
        "venues": [_venue_full(r) for r in venue_rows],
        "artists": [_artist_full(r) for r in artist_rows],
    }


def write_catalog(
    repo: Repository, path: str, generated_at: datetime | None = None
) -> int:
    if generated_at is None:
        generated_at = datetime.now(UTC)
    catalog = build_catalog(repo, generated_at=generated_at)
    parent = os.path.dirname(path)
    if parent:
        os.makedirs(parent, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        # allow_nan=False: refuse to emit NaN/Infinity. Better to fail the
        # export loudly than ship JSON that strict parsers (the web bundler)
        # reject — which previously broke the static build silently.
        json.dump(catalog, f, ensure_ascii=False, indent=2, allow_nan=False)
    return len(catalog["exhibitions"])
