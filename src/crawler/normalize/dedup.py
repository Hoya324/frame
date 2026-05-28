"""Stable natural-key hashing for entities. Pure functions, no I/O."""

from __future__ import annotations

import hashlib
from datetime import date

_HASH_LEN = 12


def _hash(*parts: str | None) -> str:
    joined = "|".join("" if p is None else p for p in parts)
    return hashlib.sha1(joined.encode("utf-8")).hexdigest()[:_HASH_LEN]


def exhibition_id(
    source: str,
    venue_name: str | None,
    title: str,
    start_date: date | None,
) -> str:
    return _hash(source, venue_name, title, start_date.isoformat() if start_date else None)


def artist_id(name_normalized: str) -> str:
    return _hash("artist", name_normalized)


def venue_id(name: str, normalized_address: str | None) -> str:
    if normalized_address:
        return _hash("venue:addr", normalized_address)
    return _hash("venue:name", name)


def organizer_id(name_normalized: str) -> str:
    return _hash("organizer", name_normalized)
