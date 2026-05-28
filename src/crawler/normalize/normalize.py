"""RawExhibition → NormalizedExhibition. Pure function over Raw input."""

from __future__ import annotations

from datetime import UTC, datetime

from crawler.models import (
    NormalizedExhibition,
    RawExhibition,
    Status,
)
from crawler.normalize.categories import (
    map_exhibition_type,
    map_fee_type,
    map_medium,
)
from crawler.normalize.dates import parse_date_range
from crawler.normalize.dedup import exhibition_id
from crawler.normalize.text import clean_whitespace


def _opt(raw: dict, key: str) -> str | None:
    v = raw.get(key)
    if v is None:
        return None
    s = str(v).strip()
    return s or None


def normalize_exhibition(raw_payload: RawExhibition) -> NormalizedExhibition:
    raw = raw_payload.raw
    warnings: list[str] = []

    title = _opt(raw, "title")
    if not title:
        raise ValueError("title is required to normalize an exhibition")
    title = clean_whitespace(title)

    date_range_text = _opt(raw, "date_range")
    start_date, end_date = parse_date_range(date_range_text)
    if date_range_text and start_date is None:
        warnings.append("date_range")

    medium_text = " ".join(
        filter(None, [title, _opt(raw, "description"), _opt(raw, "category")])
    )
    medium = map_medium(medium_text)

    exhibition_type = map_exhibition_type(_opt(raw, "exhibition_type_text") or "")

    price_min = raw.get("price_min")
    price_max = raw.get("price_max")
    fee_type = map_fee_type(_opt(raw, "fee_text"), price_min, price_max)

    now = datetime.now(UTC)

    return NormalizedExhibition(
        id=exhibition_id(
            raw_payload.source.value,
            _opt(raw, "venue_name"),
            title,
            start_date,
        ),
        source=raw_payload.source,
        source_url=raw_payload.source_url,
        title=title,
        title_en=_opt(raw, "title_en"),
        description=_opt(raw, "description"),
        poster_image_url=_opt(raw, "poster_image_url"),
        medium=medium,
        exhibition_type=exhibition_type,
        genre_tags=raw.get("genre_tags") or [],
        fee_type=fee_type,
        price_min=price_min,
        price_max=price_max,
        activities=raw.get("activities") or [],
        start_date=start_date,
        end_date=end_date,
        open_hours=_opt(raw, "open_hours"),
        artist_raw_names=raw.get("artists") or [],
        venue_raw_name=_opt(raw, "venue_name"),
        venue_raw_region=_opt(raw, "venue_region"),
        organizer_raw_name=_opt(raw, "organizer"),
        status=Status.UNKNOWN,
        crawled_at=now,
        updated_at=now,
        warnings=warnings,
    )
