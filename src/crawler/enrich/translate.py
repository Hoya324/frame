# src/crawler/enrich/translate.py
"""Backfill per-locale translations for exhibition/venue/artist text fields.

Idempotent: only fills locale/field combinations that are missing from each
row's existing ``tr`` JSON. Source language is detected per field by script;
we never translate a field into its own source language.
"""

from __future__ import annotations

import json
import logging
import time
from collections.abc import Callable
from dataclasses import dataclass

import httpx

from crawler.enrich.translator import Translator, detect_lang, targets_for
from crawler.sinks.base import Repository, SheetName

logger = logging.getLogger(__name__)

# sheet -> fields we translate. Venue and artist ``name`` are proper nouns:
# offline MT maps them to unrelated phrases (e.g. 육명심 -> "About Us"), which is
# worse than the original, so they are deliberately NOT translated. Out-of-scope
# fields are pruned from existing ``tr`` on the next run (see _backfill_sheet).
_FIELDS: dict[SheetName, tuple[str, ...]] = {
    SheetName.EXHIBITIONS: ("title", "description"),
    SheetName.VENUES: (),
    SheetName.ARTISTS: (),
}

# How many field→locale translation jobs to pack into one batched API request.
# The free tier limits requests (RPM/RPD), not tokens (TPM is huge), so batching
# many jobs per call is what makes a full rebuild finish in a run or two instead
# of thousands of single requests over many days.
_BATCH_JOBS = 20

# Stop the run after this many consecutive *quota* (429) batch failures — that
# means every key's daily request quota is exhausted, so hammering on only burns
# time and the next day's quota. Transient 503s (Gemini overload) do NOT count:
# they recover, and the time budget already bounds a sustained-503 run. The
# cleared/unfilled rows resume on the next run once quota resets.
_MAX_CONSECUTIVE_QUOTA_FAILS = 5


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
    deadline: float | None,
    now: Callable[[], float],
    reset: bool,
) -> tuple[int, int, int, int, bool]:
    rows = repo.read_rows(sheet)
    pending: list[dict] = []
    rows_patched = 0
    fields_translated = 0
    errors = 0
    stopped = False

    def flush() -> None:
        nonlocal rows_patched
        if pending:
            repo.patch_rows(sheet, list(pending))
            rows_patched += len(pending)
            pending.clear()

    # Reset: clear in-scope translations from EVERY row first (cheap, no API),
    # persisting the cleared state. The fill loop below then treats those fields
    # as missing and refills them with the current engine. Unlike an in-place
    # overwrite this survives a budget cut — rows this pass never reaches are
    # still cleared, so the recurring incremental backfill resumes and converges
    # (an overwrite would leave stale translations that later runs skip).
    if reset:
        for row in rows:
            try:
                existing = json.loads(row.get("tr") or "{}")
            except (ValueError, TypeError):
                existing = {}
            if not isinstance(existing, dict):
                existing = {}
            cleared = False
            for loc in list(existing.keys()):
                bucket = existing[loc]
                if not isinstance(bucket, dict):
                    del existing[loc]
                    cleared = True
                    continue
                for f in [k for k in bucket if k in fields]:
                    del bucket[f]
                    cleared = True
                if not bucket:
                    del existing[loc]
            if cleared:
                # Mutate the in-memory row so the fill loop below sees it cleared
                # without a re-read; the patch persists it for the next run.
                row["tr"] = json.dumps(existing, ensure_ascii=False) if existing else ""
                pending.append({
                    "id": row["id"],
                    "tr": row["tr"],
                    "lang": _row_lang(row, fields) if existing else "",
                })
                if len(pending) >= flush_every:
                    flush()
        flush()

    # Fill missing translations, buffering many field→locale jobs across rows so
    # they go out in one batched request (the free tier caps requests, not
    # tokens). Each work item keeps its row's parsed ``tr`` and the jobs it still
    # needs; run_batch() translates the whole buffer at once and writes results
    # back. A row whose only change is a prune still gets patched (no jobs).
    work: list[dict] = []
    pending_jobs = 0
    consecutive_quota_fails = 0
    circuit_open = False

    def run_batch() -> None:
        nonlocal fields_translated, errors, pending_jobs
        nonlocal consecutive_quota_fails, circuit_open
        if not work:
            return
        jobs = [(text, src, loc) for w in work for (_f, loc, text, src) in w["jobs"]]
        results: list[str] | None = None
        if jobs:
            try:
                results = translator.translate_batch(jobs)
                consecutive_quota_fails = 0
            except Exception as exc:
                logger.exception("translate_batch failed for %d jobs", len(jobs))
                results = None
                # Only a 429 (quota) trips the breaker; transient 503s recover and
                # must not count, or a brief Gemini overload aborts the whole run.
                is_quota = (
                    isinstance(exc, httpx.HTTPStatusError)
                    and exc.response.status_code == 429
                )
                if is_quota:
                    consecutive_quota_fails += 1
                    if consecutive_quota_fails >= _MAX_CONSECUTIVE_QUOTA_FAILS:
                        circuit_open = True
        idx = 0
        for w in work:
            existing = w["existing"]
            changed = w["changed"]
            for field, loc, _text, _src in w["jobs"]:
                if results is not None:
                    existing.setdefault(loc, {})[field] = results[idx]
                    fields_translated += 1
                    changed = True
                else:
                    errors += 1
                idx += 1
            if changed:
                pending.append({
                    "id": w["row"]["id"],
                    # Cleared to empty when pruning leaves no translations, so a
                    # sheet dropped from scope ends up with blank tr/lang again.
                    "tr": json.dumps(existing, ensure_ascii=False) if existing else "",
                    "lang": _row_lang(w["row"], fields) if existing else "",
                })
                if len(pending) >= flush_every:
                    flush()
        work.clear()
        pending_jobs = 0

    for row in rows:
        if circuit_open or (deadline is not None and now() >= deadline):
            stopped = True
            break
        try:
            existing = json.loads(row.get("tr") or "{}")
        except (ValueError, TypeError):
            existing = {}
        if not isinstance(existing, dict):
            existing = {}

        changed = False

        # Prune translations whose field is no longer in scope (e.g. proper-noun
        # name fields we stopped translating). Re-running the backfill after a
        # scope change self-heals stale/garbage translations out of the sheet.
        for loc in list(existing.keys()):
            bucket = existing[loc]
            if not isinstance(bucket, dict):
                del existing[loc]
                changed = True
                continue
            for f in [k for k in bucket if k not in fields]:
                del bucket[f]
                changed = True
            if not bucket:
                del existing[loc]

        # Collect the field→locale jobs this row still needs (reset already
        # cleared stale ones above, so this only fills fresh gaps — resumable).
        jobs: list[tuple[str, str, str, str]] = []
        for field in fields:
            text = str(row.get(field) or "").strip()
            if not text:
                continue
            src = detect_lang(text)
            for loc in targets_for(src):
                if (existing.get(loc) or {}).get(field):
                    continue  # already translated — idempotent skip
                jobs.append((field, loc, text, src))

        work.append({"row": row, "existing": existing, "changed": changed, "jobs": jobs})
        pending_jobs += len(jobs)
        if pending_jobs >= _BATCH_JOBS:
            run_batch()

    run_batch()
    flush()
    return len(rows), rows_patched, fields_translated, errors, stopped


def backfill_translations(
    repo: Repository,
    translator: Translator,
    flush_every: int = 25,
    max_seconds: float | None = None,
    now: Callable[[], float] = time.monotonic,
    reset: bool = False,
) -> TranslationReport:
    # Flush patches in batches so a partial run (e.g. a CI timeout mid-backfill)
    # persists what it finished. Re-runs skip already-translated rows, so the
    # backfill converges across runs instead of losing a whole sheet's work.
    #
    # max_seconds bounds the wall-clock budget: when exhausted the backfill stops
    # (after flushing) so the CI job's later export/commit steps still run. The
    # next run resumes where this one left off, so the JSON refreshes every run.
    deadline = None if max_seconds is None else now() + max_seconds
    seen = patched = translated = errors = 0
    for sheet, fields in _FIELDS.items():
        s, p, t, e, stopped = _backfill_sheet(
            repo, sheet, fields, translator, flush_every, deadline, now, reset
        )
        seen += s
        patched += p
        translated += t
        errors += e
        if stopped:
            break
    return TranslationReport(seen, patched, translated, errors)
