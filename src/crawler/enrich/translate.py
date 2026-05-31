# src/crawler/enrich/translate.py
"""Backfill per-locale translations for exhibition/venue/artist text fields.

Idempotent: only fills locale/field combinations that are missing from each
row's existing ``tr`` JSON. Source language is detected per field by script;
we never translate a field into its own source language.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass

from crawler.enrich.translator import Translator, detect_lang, targets_for
from crawler.sinks.base import Repository, SheetName

logger = logging.getLogger(__name__)

# sheet -> fields we translate
_FIELDS: dict[SheetName, tuple[str, ...]] = {
    SheetName.EXHIBITIONS: ("title", "description"),
    SheetName.VENUES: ("name",),
    SheetName.ARTISTS: ("name",),
}


@dataclass(frozen=True)
class TranslationReport:
    rows_seen: int
    rows_patched: int
    fields_translated: int
    errors: int


def _row_lang(row: dict, fields: tuple[str, ...]) -> str:
    """Record-level language label, taken from the first non-empty field."""
    for f in fields:
        text = str(row.get(f) or "").strip()
        if text:
            return detect_lang(text)
    return "ko"


def _backfill_sheet(
    repo: Repository,
    sheet: SheetName,
    fields: tuple[str, ...],
    translator: Translator,
    flush_every: int,
) -> tuple[int, int, int, int]:
    rows = repo.read_rows(sheet)
    pending: list[dict] = []
    rows_patched = 0
    fields_translated = 0
    errors = 0

    def flush() -> None:
        nonlocal rows_patched
        if pending:
            repo.patch_rows(sheet, list(pending))
            rows_patched += len(pending)
            pending.clear()

    for row in rows:
        try:
            existing = json.loads(row.get("tr") or "{}")
        except (ValueError, TypeError):
            existing = {}
        if not isinstance(existing, dict):
            existing = {}

        changed = False
        for field in fields:
            text = str(row.get(field) or "").strip()
            if not text:
                continue
            src = detect_lang(text)
            for loc in targets_for(src):
                bucket = existing.setdefault(loc, {})
                if bucket.get(field):
                    continue  # already translated — idempotent skip
                try:
                    bucket[field] = translator.translate(text, src, loc)
                    fields_translated += 1
                    changed = True
                except Exception:
                    logger.exception(
                        "translate failed: sheet=%s id=%s field=%s %s->%s",
                        sheet, row.get("id"), field, src, loc,
                    )
                    errors += 1

        if changed:
            pending.append({
                "id": row["id"],
                "tr": json.dumps(existing, ensure_ascii=False),
                "lang": _row_lang(row, fields),
            })
            if len(pending) >= flush_every:
                flush()

    flush()
    return len(rows), rows_patched, fields_translated, errors


def backfill_translations(
    repo: Repository, translator: Translator, flush_every: int = 25
) -> TranslationReport:
    # Flush patches in batches so a partial run (e.g. a CI timeout mid-backfill)
    # persists what it finished. Re-runs skip already-translated rows, so the
    # backfill converges across runs instead of losing a whole sheet's work.
    seen = patched = translated = errors = 0
    for sheet, fields in _FIELDS.items():
        s, p, t, e = _backfill_sheet(repo, sheet, fields, translator, flush_every)
        seen += s
        patched += p
        translated += t
        errors += e
    return TranslationReport(seen, patched, translated, errors)
