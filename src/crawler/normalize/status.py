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


def status_patches_for_all(today: date, rows: list[dict]) -> list[dict]:
    """Return upsert patches that update `status` for any row whose
    computed status differs from the stored value.

    Reads ``start_date``, ``end_date``, ``id``, ``status`` from each row.
    Rows where ``id`` is missing or empty are skipped.
    Date fields may be ISO-format strings or empty strings.
    """
    patches: list[dict] = []
    for row in rows:
        row_id = row.get("id")
        if not row_id:
            continue

        start_raw = row.get("start_date") or ""
        end_raw = row.get("end_date") or ""
        start = date.fromisoformat(start_raw) if start_raw else None
        end = date.fromisoformat(end_raw) if end_raw else None

        new_status = compute_status(today, start, end)
        if new_status.value != row.get("status"):
            patches.append({"id": row_id, "status": new_status.value})
    return patches
