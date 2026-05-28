"""Derive Status from today + date range."""

from __future__ import annotations

from datetime import date

from crawler.models import Status


def compute_status(
    today: date,
    start: date | None,
    end: date | None,
) -> Status:
    if start is None:
        return Status.UNKNOWN
    if today < start:
        return Status.UPCOMING
    if end is not None and today > end:
        return Status.PAST
    return Status.ONGOING
