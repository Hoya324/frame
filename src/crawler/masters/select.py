"""Select a master's representative works from their configured museum sources."""

from __future__ import annotations

import logging

from crawler.masters.models import MasterSeed, RawWork
from crawler.masters.museums.base import MuseumClient

logger = logging.getLogger(__name__)


def _rank_key(w: RawWork) -> tuple:
    # Higher tuple sorts first under reverse=True: highlight, has-year, has-thumb.
    return (w.is_highlight, w.year is not None, w.thumb_url is not None)


def select_works(
    seed: MasterSeed,
    clients: dict[str, MuseumClient],
    cap: int = 10,
) -> list[RawWork]:
    """Gather, filter, rank and cap a master's works.

    Explicit ``object_ids`` keep their authored order and are placed before any
    auto-pulled (query) results. Everything is filtered to public-domain works
    that actually carry an image, and deduped by ``work_id``."""
    explicit: list[RawWork] = []
    pulled: list[RawWork] = []
    for sq in seed.sources:
        client = clients.get(sq.source)
        if client is None:
            continue
        # A single source failing (network, 403, rate limit) must not sink the
        # whole master — skip that source and keep whatever the others return.
        try:
            if sq.object_ids:
                explicit.extend(client.fetch_by_ids(sq.object_ids))
            elif sq.query and sq.artist:
                pulled.extend(client.search_works(sq.query, limit=cap, artist=sq.artist))
            elif sq.query:
                pulled.extend(client.search_works(sq.query, limit=cap))
        except Exception:
            logger.warning(
                "masters: source %s failed for %s; skipping", sq.source, seed.id,
                exc_info=True,
            )

    pulled.sort(key=_rank_key, reverse=True)

    excludes = [t.lower() for t in seed.exclude_titles]
    out: list[RawWork] = []
    seen: set[str] = set()
    for w in [*explicit, *pulled]:
        if not (w.is_public_domain and w.has_image):
            continue
        if any(t in w.title.lower() for t in excludes):
            continue
        if w.work_id in seen:
            continue
        seen.add(w.work_id)
        out.append(w)
        if len(out) >= cap:
            break
    return out
