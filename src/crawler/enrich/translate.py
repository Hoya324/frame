# src/crawler/enrich/translate.py
"""Backfill per-locale translations for exhibition/venue/artist text fields.

Idempotent: only fills locale/field combinations that are missing from each
row's existing ``tr`` JSON. Source language is detected per field by script;
we never translate a field into its own source language.
"""

from __future__ import annotations

import json
import logging
import os
import time
from collections.abc import Callable
from dataclasses import dataclass

from crawler.enrich.translator import (
    Translator,
    _gemini_is_daily_429,
    detect_lang,
    targets_for,
)
from crawler.sinks.base import Repository, SheetName

logger = logging.getLogger(__name__)

# sheet -> fields we translate. Venue/artist ``name`` are proper nouns; the LLM
# translator preserves them (transliterating rather than mistranslating, e.g.
# 캐논 갤러리 -> "Canon Gallery" / キヤノンギャラリー), so they're now in scope.
# Fields removed from scope here are pruned from existing ``tr`` on the next run.
_FIELDS: dict[SheetName, tuple[str, ...]] = {
    SheetName.EXHIBITIONS: ("title", "description"),
    SheetName.VENUES: ("name",),
    SheetName.ARTISTS: ("name",),
}

# How many field→locale translation jobs to pack into one batched API request.
# The free tier limits requests (RPM/RPD), not tokens, so batching is the
# throughput lever — but too large a batch makes the model's generation slow
# enough to hit the request timeout, so keep it modest. Override GEMINI_BATCH_JOBS.
_BATCH_JOBS = 10

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
    # Total field→locale jobs that were missing at the start of this run (the
    # whole backlog, regardless of the time budget). ``fields_remaining`` below
    # is the slice this run didn't get to — the convergence signal a CI summary
    # needs to tell "still working through it" apart from "done / stuck".
    fields_pending: int = 0

    @property
    def fields_remaining(self) -> int:
        """In-scope translations still missing after this run (pending minus done)."""
        return max(0, self.fields_pending - self.fields_translated)


def _row_lang(row: dict, fields: tuple[str, ...]) -> str:
    """Record-level language label, taken from the first non-empty field."""
    for f in fields:
        text = str(row.get(f) or "").strip()
        if text:
            return detect_lang(text)
    return "ko"


def _parse_tr(row: dict) -> dict:
    try:
        existing = json.loads(row.get("tr") or "{}")
    except (ValueError, TypeError):
        existing = {}
    return existing if isinstance(existing, dict) else {}


def _round_robin(lists: list[list]) -> list:
    """Merge per-sheet lists by taking one item from each in turn. Interleaving
    the work means a budget/quota cut spreads across sheets instead of letting
    the first (largest) sheet consume the whole run before the others get a turn."""
    iters = [iter(lst) for lst in lists]
    done = [False] * len(iters)
    out: list = []
    while not all(done):
        for i, it in enumerate(iters):
            if done[i]:
                continue
            try:
                out.append(next(it))
            except StopIteration:
                done[i] = True
    return out


def _collect_work(
    repo: Repository,
    sheet: SheetName,
    fields: tuple[str, ...],
    reset: bool,
    queue_patch: Callable[[SheetName, tuple[str, ...], dict, dict], None],
    flush: Callable[[SheetName], None],
) -> tuple[int, list[dict]]:
    """Read a sheet, apply the reset-clear and out-of-scope prune (queuing those
    no-API patches), and return the work items still needing translation."""
    rows = repo.read_rows(sheet)

    # Reset: clear in-scope translations from EVERY row first (cheap, no API),
    # persisting the cleared state so a budget-cut run still resumes from empty
    # (an in-place overwrite would strand stale translations later runs skip).
    if reset:
        for row in rows:
            existing = _parse_tr(row)
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
                # Mutate the in-memory row so the collection below sees it cleared.
                row["tr"] = json.dumps(existing, ensure_ascii=False) if existing else ""
                queue_patch(sheet, fields, row, existing)
        flush(sheet)

    work: list[dict] = []
    for row in rows:
        existing = _parse_tr(row)
        changed = False
        # Prune translations whose field is no longer in scope — self-heals stale
        # data (e.g. fields dropped from scope) on the next run.
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
        work.append({
            "sheet": sheet, "fields": fields, "row": row,
            "existing": existing, "changed": changed, "jobs": jobs,
        })
    return len(rows), work


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
    # max_seconds bounds the wall-clock budget; when exhausted the run stops after
    # flushing so the next run resumes. Work from all sheets is interleaved
    # round-robin so the largest sheet can't consume the whole run's quota before
    # the smaller ones (e.g. venue/artist names) get any.
    deadline = None if max_seconds is None else now() + max_seconds
    batch_jobs = max(1, int(os.environ.get("GEMINI_BATCH_JOBS", _BATCH_JOBS)))

    pending: dict[SheetName, list[dict]] = {sheet: [] for sheet in _FIELDS}
    rows_patched = 0
    fields_translated = 0
    errors = 0

    def flush(sheet: SheetName) -> None:
        nonlocal rows_patched
        if pending[sheet]:
            repo.patch_rows(sheet, list(pending[sheet]))
            rows_patched += len(pending[sheet])
            pending[sheet].clear()

    def queue_patch(
        sheet: SheetName, fields: tuple[str, ...], row: dict, existing: dict
    ) -> None:
        pending[sheet].append({
            "id": row["id"],
            # Cleared to empty when no translation survives (e.g. a reset or an
            # out-of-scope prune), but `lang` is a script-detected source label,
            # independent of translation — record it regardless so downstream
            # consumers see correct metadata even before/without any tr.
            "tr": json.dumps(existing, ensure_ascii=False) if existing else "",
            "lang": _row_lang(row, fields),
        })
        if len(pending[sheet]) >= flush_every:
            flush(sheet)

    # Phase 1: read every sheet, apply reset-clear + prune, collect remaining work.
    seen = 0
    per_sheet_work: list[list[dict]] = []
    for sheet, fields in _FIELDS.items():
        s, work = _collect_work(repo, sheet, fields, reset, queue_patch, flush)
        seen += s
        per_sheet_work.append(work)
    work_items = _round_robin(per_sheet_work)
    # The full translation backlog at run start — what the CI summary divides
    # into "done this run" vs "still remaining" so progress is legible.
    fields_pending = sum(len(item["jobs"]) for item in work_items)

    # Phase 2: fill missing translations, batching many field→locale jobs into one
    # request (the free tier caps requests, not tokens). Items carry their sheet,
    # so a mixed batch's results are written back to the right rows.
    work_buf: list[dict] = []
    buf_jobs = 0
    consecutive_quota_fails = 0
    circuit_open = False

    def run_batch() -> None:
        nonlocal fields_translated, errors, buf_jobs
        nonlocal consecutive_quota_fails, circuit_open
        if not work_buf:
            return
        jobs = [(text, src, loc) for w in work_buf for (_f, loc, text, src) in w["jobs"]]
        results: list[str] | None = None
        if jobs:
            try:
                results = translator.translate_batch(jobs)
                consecutive_quota_fails = 0
            except Exception as exc:
                logger.exception("translate_batch failed for %d jobs", len(jobs))
                results = None
                # Only a per-DAY quota 429 trips the breaker — that means the
                # day's request budget is gone, so retrying only burns time and
                # tomorrow's quota. Transient 503s (overload) and per-MINUTE 429s
                # (RPM spikes) recover on their own — the translator's retry/backoff
                # absorbs them — so they must NOT count, or a brief blip would abort
                # a run whose daily quota is fine ("quota left but it stopped"). The
                # time budget bounds a run that keeps hitting transient limits.
                if _gemini_is_daily_429(exc):
                    consecutive_quota_fails += 1
                    if consecutive_quota_fails >= _MAX_CONSECUTIVE_QUOTA_FAILS:
                        circuit_open = True
                else:
                    consecutive_quota_fails = 0
        idx = 0
        for w in work_buf:
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
                queue_patch(w["sheet"], w["fields"], w["row"], existing)
        work_buf.clear()
        buf_jobs = 0

    for item in work_items:
        if circuit_open or (deadline is not None and now() >= deadline):
            break
        work_buf.append(item)
        buf_jobs += len(item["jobs"])
        if buf_jobs >= batch_jobs:
            run_batch()
    run_batch()
    for sheet in _FIELDS:
        flush(sheet)

    return TranslationReport(
        seen, rows_patched, fields_translated, errors, fields_pending=fields_pending
    )
