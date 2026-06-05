"""Export the canonical store to a denormalized JSON snapshot for the web frontend."""

from __future__ import annotations

import json
import logging
import math
import os
import re
from datetime import UTC, datetime

from crawler.normalize.text import sanitize_description
from crawler.sinks.base import Repository, SheetName

log = logging.getLogger(__name__)


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


def _tr(value: object) -> dict:
    """Parse the stored ``tr`` JSON column into a nested {locale:{field:text}} dict.

    Translated ``description`` fields are sanitized on the way out — they are
    LLM translations of the source description and inherit the same leaked
    <script>/email chrome, so the published snapshot stays clean even when the
    sheet row predates the crawl-time sanitization."""
    if not value:
        return {}
    try:
        parsed = json.loads(value) if isinstance(value, str) else value
    except (ValueError, TypeError):
        return {}
    if not isinstance(parsed, dict):
        return {}
    for bucket in parsed.values():
        if isinstance(bucket, dict) and bucket.get("description"):
            cleaned = sanitize_description(bucket["description"])
            if cleaned:
                bucket["description"] = cleaned
            else:
                del bucket["description"]
    return parsed


# Sources that crawl all art genres, not just photography. Their rows are only
# kept when the classified medium is photo-adjacent. Every other source is
# photo-dedicated (or already photo-filtered at the source), so its rows are
# always kept regardless of medium.
_GENERAL_SOURCES = {"artmap", "naver"}
_PHOTO_MEDIUMS = {"photo", "video", "gear"}


def _is_photo_relevant(row: dict) -> bool:
    if _str_or_none(row.get("source")) not in _GENERAL_SOURCES:
        return True
    return _str_or_none(row.get("medium")) in _PHOTO_MEDIUMS


# Aggregator sources re-list exhibitions that originate elsewhere (the venue's
# own site, an official museum feed). When the same show is crawled both from
# its primary source and from an aggregator, the two rows carry different ids
# (the natural key in normalize/dedup.py includes `source`), so the id-collapse
# above can't merge them. We collapse them here, preferring the primary
# (non-aggregator) row. tokyo_art_beat is Japan's cross-venue aggregator, the
# JP analogue of artmap.
_AGGREGATOR_SOURCES = {"artmap", "naver", "tokyo_art_beat"}

# Title noise stripped before matching: bracket/quote ornaments and all
# whitespace. Two sources punctuate the same title differently, so we compare
# the bare characters.
_DEDUP_STRIP = re.compile(r"[《》「」『』\"'“”‘’()\[\]\s]")


def _dedup_title_key(title: object) -> str:
    if not title:
        return ""
    return _DEDUP_STRIP.sub("", str(title)).lower()


def _primary_sort_key(row: dict) -> tuple:
    """Order duplicates so the most authoritative/complete row sorts first.

    Primary source beats aggregator; then richer description, more artists, a
    poster; finally the id for a stable, deterministic tiebreak."""
    src = _str_or_none(row.get("source")) or ""
    return (
        0 if src not in _AGGREGATOR_SOURCES else 1,
        -len(_str_or_none(row.get("description")) or ""),
        -len(_split(row.get("artist_ids"))),
        0 if _str_or_none(row.get("poster_image_url")) else 1,
        _id(row.get("id")),
    )


def _merge_duplicate(members: list[dict]) -> dict:
    """Collapse a set of duplicate rows into one, keeping the primary row's
    prose (description/poster stay internally consistent with its `source`)
    while grafting on the union of every member's artist/genre associations so
    the merge never drops data the aggregator carried but the primary lacked."""
    winner = dict(min(members, key=_primary_sort_key))
    artist_ids = _split(winner.get("artist_ids"))
    genres = _split(winner.get("genre_tags"))
    seen_a, seen_g = set(artist_ids), set(genres)
    for row in members:
        for aid in _split(row.get("artist_ids")):
            if aid not in seen_a:
                seen_a.add(aid)
                artist_ids.append(aid)
        for genre in _split(row.get("genre_tags")):
            if genre not in seen_g:
                seen_g.add(genre)
                genres.append(genre)
    winner["artist_ids"] = ",".join(artist_ids)
    winner["genre_tags"] = ",".join(genres)
    return winner


def _collapse_cross_source(rows: list[dict]) -> list[dict]:
    """Merge cross-source duplicates keyed on (normalized title, start, end).

    The (title, start, end) triple is tight enough that recurring annual shows
    (same title, different dates) stay separate, while the same exhibition
    listed by two sources collapses to one. Rows missing a title or start_date
    can't be matched safely, so they pass through untouched. Output order
    follows first appearance, so the snapshot stays stable run-to-run."""
    slots: dict[tuple, int] = {}
    buckets: list[list[dict]] = []
    for row in rows:
        title_key = _dedup_title_key(row.get("title"))
        start = _str_or_none(row.get("start_date"))
        if not title_key or not start:
            buckets.append([row])
            continue
        key = (title_key, start, _str_or_none(row.get("end_date")))
        if key in slots:
            buckets[slots[key]].append(row)
        else:
            slots[key] = len(buckets)
            buckets.append([row])

    collapsed = 0
    out: list[dict] = []
    for members in buckets:
        if len(members) == 1:
            out.append(members[0])
            continue
        collapsed += len(members) - 1
        out.append(_merge_duplicate(members))
    if collapsed:
        log.info("collapsed %d cross-source duplicate exhibition(s)", collapsed)
    return out


def _venue_full(row: dict) -> dict:
    return {
        "id": _id(row["id"]),
        "name": row.get("name", ""),
        "lang": _str_or_none(row.get("lang")),
        "tr": _tr(row.get("tr")),
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
        "lang": _str_or_none(row.get("lang")),
        "tr": _tr(row.get("tr")),
        "region": _str_or_none(row.get("region")),
        "district": _str_or_none(row.get("district")),
        "lat": _float_or_none(row.get("latitude")),
        "lng": _float_or_none(row.get("longitude")),
    }


def _artist_full(row: dict) -> dict:
    return {
        "id": _id(row["id"]),
        "name": row.get("name", ""),
        "lang": _str_or_none(row.get("lang")),
        "tr": _tr(row.get("tr")),
    }


def _exhibition_json(row: dict, venues: dict[str, dict], artists: dict[str, dict]) -> dict:
    venue_id = _str_or_none(row.get("venue_id"))
    venue_row = venues.get(venue_id) if venue_id else None
    artist_ids = _split(row.get("artist_ids"))
    return {
        "id": _id(row["id"]),
        "source": _str_or_none(row.get("source")),
        "title": row.get("title", ""),
        "lang": _str_or_none(row.get("lang")),
        "tr": _tr(row.get("tr")),
        "poster_image_url": _str_or_none(row.get("poster_image_url")),
        "description": _str_or_none(sanitize_description(_str_or_none(row.get("description")))),
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
            {
                "id": _id(artists[aid]["id"]),
                "name": artists[aid]["name"],
                "lang": _str_or_none(artists[aid].get("lang")),
                "tr": _tr(artists[aid].get("tr")),
            }
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

    # Collapse any duplicate exhibition ids that predate the upsert in-batch
    # dedupe fix, so the snapshot never ships the same exhibition twice.
    deduped_rows: dict[str, dict] = {}
    for r in exhibition_rows:
        rid = _id(r["id"]) if r.get("id") else None
        if rid is None:
            continue
        deduped_rows[rid] = r

    kept_rows = [r for r in deduped_rows.values() if _is_photo_relevant(r)]
    # Merge the same exhibition listed by both its primary source and an
    # aggregator (different ids, so the id-collapse above misses them).
    kept_rows = _collapse_cross_source(kept_rows)

    # Drop venues/artists that no surviving exhibition references, so the
    # region dropdown and other reference lists don't surface dead entries.
    referenced_venues = {_str_or_none(r.get("venue_id")) for r in kept_rows}
    referenced_artists = {
        aid for r in kept_rows for aid in _split(r.get("artist_ids"))
    }

    return {
        "generated_at": generated_at.isoformat(),
        "exhibitions": [
            _exhibition_json(r, venues_by_id, artists_by_id) for r in kept_rows
        ],
        "venues": [
            _venue_full(r) for r in venue_rows if _id(r["id"]) in referenced_venues
        ],
        "artists": [
            _artist_full(r)
            for r in artist_rows
            if _id(r["id"]) in referenced_artists
        ],
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
