# tests/enrich/test_translate.py
import json

import httpx

from crawler.enrich.translate import backfill_translations
from crawler.sinks.base import SheetName


class FakeRepo:
    def __init__(self, rows):
        self._rows = {SheetName.EXHIBITIONS: rows.get("exh", []),
                      SheetName.VENUES: rows.get("ven", []),
                      SheetName.ARTISTS: rows.get("art", [])}
        self.patched = {}
        self.patch_calls = {}  # sheet -> list of per-flush row batches

    def read_rows(self, sheet):
        return [dict(r) for r in self._rows[sheet]]

    def patch_rows(self, sheet, rows):
        self.patch_calls.setdefault(sheet, []).append(list(rows))
        self.patched[sheet] = [r for batch in self.patch_calls[sheet] for r in batch]

    def append_rows(self, sheet, rows): ...
    def clear_sheet(self, sheet): ...


class FakeTranslator:
    def __init__(self):
        self.batch_calls = []  # list of job-count per translate_batch call

    def translate(self, text, from_code, to_code):
        return f"[{to_code}]{text}"

    def translate_batch(self, jobs):
        self.batch_calls.append(len(jobs))
        return [f"[{to}]{text}" for text, _src, to in jobs]


def test_fills_missing_translations_for_japanese_exhibition():
    repo = FakeRepo({"exh": [
        {"id": "e1", "title": "戎康友 展", "description": "カリフォルニア", "tr": "", "lang": ""},
    ]})
    backfill_translations(repo, FakeTranslator())

    patched = {r["id"]: r for r in repo.patched[SheetName.EXHIBITIONS]}
    row = patched["e1"]
    assert row["lang"] == "ja"
    tr = json.loads(row["tr"])
    assert tr["ko"]["title"] == "[ko]戎康友 展"
    assert tr["en"]["description"] == "[en]カリフォルニア"
    assert "ja" not in tr  # 원문 언어로는 번역하지 않는다


def test_idempotent_skips_existing():
    existing = json.dumps({"ko": {"title": "KEEP"}})
    repo = FakeRepo({"exh": [
        {"id": "e1", "title": "戎康友 展", "description": "", "tr": existing, "lang": "ja"},
    ]})
    backfill_translations(repo, FakeTranslator())
    tr = json.loads({r["id"]: r for r in repo.patched[SheetName.EXHIBITIONS]}["e1"]["tr"])
    assert tr["ko"]["title"] == "KEEP"          # 기존 값 보존
    assert tr["en"]["title"] == "[en]戎康友 展"  # 누락분만 채움


def test_backfill_batches_many_fields_into_few_requests():
    # 10 Korean exhibitions, each title+description -> en+ja = 4 jobs = 40 jobs.
    # The free tier caps requests, not tokens, so these must collapse into a few
    # translate_batch calls instead of 40 single requests.
    rows = [{"id": f"e{i}", "title": f"제목{i}", "description": f"설명{i}",
             "tr": "", "lang": ""} for i in range(10)]
    repo = FakeRepo({"exh": rows})
    tr = FakeTranslator()
    backfill_translations(repo, tr)
    assert sum(tr.batch_calls) == 40        # every field/locale translated
    assert len(tr.batch_calls) < 40         # but in far fewer requests
    out = {r["id"]: r for r in repo.patched[SheetName.EXHIBITIONS]}
    tr0 = json.loads(out["e0"]["tr"])
    assert tr0["en"]["title"] == "[en]제목0"
    assert tr0["ja"]["description"] == "[ja]설명0"


def test_backfill_batch_size_is_env_configurable(monkeypatch):
    # Smaller batches keep each request fast enough to beat the timeout.
    monkeypatch.setenv("GEMINI_BATCH_JOBS", "4")
    rows = [{"id": f"e{i}", "title": f"제목{i}", "description": f"설명{i}",
             "tr": "", "lang": ""} for i in range(10)]  # 10 * 4 jobs = 40
    repo = FakeRepo({"exh": rows})
    tr = FakeTranslator()
    backfill_translations(repo, tr)
    assert sum(tr.batch_calls) == 40
    assert all(n <= 4 for n in tr.batch_calls)  # honored the cap


def test_report_tracks_pending_and_remaining_backlog():
    # The CI summary needs the full backlog to show convergence. Two Korean
    # exhibitions, title+description each -> en+ja = 4 jobs/row = 8 pending.
    rows = [{"id": f"e{i}", "title": f"제목{i}", "description": f"설명{i}",
             "tr": "", "lang": ""} for i in range(2)]
    repo = FakeRepo({"exh": rows})
    report = backfill_translations(repo, FakeTranslator())
    assert report.fields_pending == 8
    assert report.fields_translated == 8
    assert report.fields_remaining == 0   # fully caught up


def test_report_remaining_reflects_unfinished_work_on_budget_cut():
    # A zero time budget stops before any batch runs, so the whole backlog is
    # still pending and 'remaining' equals it — the "not done yet" signal.
    rows = [{"id": f"e{i}", "title": f"제목{i}", "description": "",
             "tr": "", "lang": ""} for i in range(3)]   # title -> en+ja = 6 jobs
    repo = FakeRepo({"exh": rows})
    report = backfill_translations(repo, FakeTranslator(), max_seconds=0.0001,
                                   now=iter([0.0, 1.0, 2.0, 3.0, 4.0]).__next__)
    assert report.fields_pending == 6
    assert report.fields_translated == 0
    assert report.fields_remaining == 6


def _daily_429():
    # A per-day quota 429 carries a QuotaFailure violation whose id names a
    # PerDay quota — that's what marks the daily budget as truly exhausted.
    req = httpx.Request("POST", "https://x/")
    resp = httpx.Response(
        429,
        request=req,
        json={"error": {"details": [
            {"@type": "type.googleapis.com/google.rpc.QuotaFailure",
             "violations": [{"quotaId": "GenerateRequestsPerDayPerProjectPerModel-FreeTier"}]},
        ]}},
    )
    return httpx.HTTPStatusError("rate limited", request=req, response=resp)


def _per_minute_429():
    # A per-minute (RPM) 429 names a PerMinute quota and clears within seconds —
    # it must NOT be treated as the daily budget being exhausted.
    req = httpx.Request("POST", "https://x/")
    resp = httpx.Response(
        429,
        request=req,
        json={"error": {"details": [
            {"@type": "type.googleapis.com/google.rpc.QuotaFailure",
             "violations": [{"quotaId": "GenerateRequestsPerMinutePerProjectPerModel-FreeTier"}]},
        ]}},
    )
    return httpx.HTTPStatusError("rate limited", request=req, response=resp)


def test_backfill_gives_up_after_consecutive_daily_quota_failures():
    # When the daily request quota is exhausted every batch 429s with a PerDay
    # violation. The backfill must trip a circuit breaker and stop instead of
    # hammering every remaining row (which only burns time and the next day's
    # quota). The cleared/unfilled rows are picked up by the next run once the
    # daily quota resets.
    class FailingTranslator:
        def __init__(self):
            self.calls = 0

        def translate(self, text, from_code, to_code):
            raise _daily_429()

        def translate_batch(self, jobs):
            self.calls += 1
            raise _daily_429()

    rows = [{"id": f"e{i}", "title": f"제목{i}", "description": "", "tr": "", "lang": ""}
            for i in range(100)]
    repo = FakeRepo({"exh": rows})
    t = FailingTranslator()
    report = backfill_translations(repo, t)
    assert t.calls <= 6                 # stopped early, didn't try all ~10 batches
    assert report.fields_translated == 0


def test_backfill_does_not_give_up_on_per_minute_429():
    # A per-minute (RPM) 429 is transient — it clears within the minute and the
    # translator's own retry/backoff absorbs it. It must NOT trip the circuit
    # breaker, or a brief RPM spike would abort a run whose daily quota is fine
    # (the symptom: "quota left but it stopped"). The time budget bounds a run
    # that keeps hitting RPM limits.
    class RateLimited:
        def __init__(self):
            self.calls = 0

        def translate(self, *a):
            raise _per_minute_429()

        def translate_batch(self, jobs):
            self.calls += 1
            raise _per_minute_429()

    rows = [{"id": f"e{i}", "title": f"제목{i}", "description": "", "tr": "", "lang": ""}
            for i in range(100)]
    repo = FakeRepo({"exh": rows})
    t = RateLimited()
    backfill_translations(repo, t)
    assert t.calls >= 9   # tried every batch (~10), breaker never tripped on RPM 429


def test_backfill_does_not_give_up_on_transient_503s():
    # A brief Gemini overload (503) is transient and must NOT trip the circuit
    # breaker — only a sustained 429 (quota) should. The run keeps trying every
    # batch (the time budget bounds a truly stuck run).
    def _err(code):
        req = httpx.Request("POST", "https://x/")
        resp = httpx.Response(code, request=req)
        return httpx.HTTPStatusError("err", request=req, response=resp)

    class Overloaded:
        def __init__(self):
            self.calls = 0

        def translate(self, *a):
            raise _err(503)

        def translate_batch(self, jobs):
            self.calls += 1
            raise _err(503)

    rows = [{"id": f"e{i}", "title": f"제목{i}", "description": "", "tr": "", "lang": ""}
            for i in range(100)]
    repo = FakeRepo({"exh": rows})
    t = Overloaded()
    backfill_translations(repo, t)
    assert t.calls >= 9   # tried every batch (~10), breaker never tripped on 503


def test_backfill_interleaves_sheets_so_names_are_not_starved():
    # Exhibitions plus venues/artists. With a tight budget the old per-sheet order
    # finished exhibitions first and never reached the name sheets. Interleaving
    # must give every sheet at least some translations under the same budget.
    exh = [{"id": f"e{i}", "title": f"제목{i}", "description": "", "tr": "", "lang": ""}
           for i in range(20)]
    ven = [{"id": f"v{i}", "name": f"갤러리{i}", "tr": "", "lang": ""} for i in range(20)]
    art = [{"id": f"a{i}", "name": f"작가{i}", "tr": "", "lang": ""} for i in range(20)]
    repo = FakeRepo({"exh": exh, "ven": ven, "art": art})
    # deadline = 0 + 4; the loop advances the clock 1 per item, so ~4 items (one
    # round-robin round + a bit) get buffered before it stops.
    clock = iter([0, 0, 1, 2, 3, 4, 5, 6, 7, 8])
    backfill_translations(repo, FakeTranslator(), flush_every=100,
                          max_seconds=4, now=lambda: next(clock))
    assert SheetName.EXHIBITIONS in repo.patched
    assert SheetName.VENUES in repo.patched   # name sheets no longer starved
    assert SheetName.ARTISTS in repo.patched


def test_reset_rebuilds_existing_in_scope_translations():
    # Switching translators leaves old garbage in place because the backfill is
    # idempotent. reset=True clears in-scope fields then refills them, so a new
    # engine rebuilds the translations (here in one unbudgeted pass).
    existing = json.dumps({"ko": {"title": "OLD-GARBAGE", "description": "OLD"}})
    repo = FakeRepo({"exh": [
        {"id": "e1", "title": "戎康友 展", "description": "カリフォルニア",
         "tr": existing, "lang": "ja"},
    ]})
    backfill_translations(repo, FakeTranslator(), reset=True)
    tr = json.loads({r["id"]: r for r in repo.patched[SheetName.EXHIBITIONS]}["e1"]["tr"])
    assert tr["ko"]["title"] == "[ko]戎康友 展"          # rebuilt, not the old value
    assert tr["ko"]["description"] == "[ko]カリフォルニア"
    assert tr["en"]["title"] == "[en]戎康友 展"          # other locales filled too


def test_reset_clears_every_row_even_past_the_budget_so_a_later_run_resumes():
    # The clear phase ignores the wall-clock budget: even rows the fill phase
    # never reaches get their stale translations wiped and persisted. A later
    # incremental run (no reset) then sees them as missing and refills them, so
    # a free-tier-throttled rebuild converges across runs instead of stranding
    # old garbage that idempotent skips would never replace.
    rows = [{"id": f"e{i}", "title": f"頂上{i}", "description": "",
             "tr": json.dumps({"ko": {"title": "OLD"}}), "lang": "ja"}
            for i in range(3)]
    repo = FakeRepo({"exh": rows})
    # deadline = 0 + 1; the first fill-loop clock read (100) is already past it,
    # so the fill phase translates nothing — only the clear phase runs.
    clock = iter([0, 100, 100, 100, 100])
    backfill_translations(repo, FakeTranslator(), flush_every=100,
                          max_seconds=1, now=lambda: next(clock), reset=True)
    persisted = {r["id"]: r for r in repo.patched[SheetName.EXHIBITIONS]}
    assert set(persisted) == {"e0", "e1", "e2"}  # all cleared, none skipped
    for i in range(3):
        assert "OLD" not in (persisted[f"e{i}"]["tr"] or "")

    # Next run reads the persisted (cleared) state — model it as a fresh repo —
    # and fills the now-missing translations with the new engine, no reset.
    resumed = FakeRepo({"exh": [
        {"id": f"e{i}", "title": f"頂上{i}", "description": "",
         "tr": persisted[f"e{i}"]["tr"], "lang": persisted[f"e{i}"]["lang"]}
        for i in range(3)
    ]})
    backfill_translations(resumed, FakeTranslator())  # incremental, no reset
    out = {r["id"]: r for r in resumed.patched[SheetName.EXHIBITIONS]}
    assert json.loads(out["e0"]["tr"])["ko"]["title"] == "[ko]頂上0"


def test_korean_row_with_no_other_locales_is_left_untouched():
    repo = FakeRepo({"exh": [
        {"id": "e1", "title": "을지로의 밤", "description": "", "tr": "", "lang": ""},
    ]})
    backfill_translations(repo, FakeTranslator())
    row = {r["id"]: r for r in repo.patched[SheetName.EXHIBITIONS]}["e1"]
    tr = json.loads(row["tr"])
    assert set(tr.keys()) == {"en", "ja"}
    assert tr["ja"]["title"] == "[ja]을지로의 밤"


def test_reset_cleared_row_still_records_detected_lang():
    # `lang` is a script-detected label, independent of whether any translation
    # survives. A reset wipes a row's in-scope tr (existing -> empty), but the
    # persisted row must still carry its detected source language so downstream
    # consumers (and a later resume) see correct metadata rather than a blank.
    existing = json.dumps({"ko": {"title": "OLD"}})
    repo = FakeRepo({"exh": [
        {"id": "e1", "title": "頂上", "description": "",
         "tr": existing, "lang": "ja"},
    ]})
    # deadline=1 with a clock that's already past it: the clear phase runs and
    # persists, but the fill phase translates nothing — so the patched row's tr
    # ends up empty, exercising the "no translation, still set lang" path.
    clock = iter([0, 100, 100, 100, 100])
    backfill_translations(repo, FakeTranslator(), flush_every=100,
                          max_seconds=1, now=lambda: next(clock), reset=True)
    row = {r["id"]: r for r in repo.patched[SheetName.EXHIBITIONS]}["e1"]
    assert (row["tr"] or "") == ""   # tr cleared, nothing refilled this run
    assert row["lang"] == "ja"       # ...but lang is still recorded


def test_flushes_incrementally_so_partial_progress_persists():
    # 7 changed rows with flush_every=3 -> flush at 3, at 6, then a final flush
    # of the trailing 1 => 3 writes. A CI timeout after any flush keeps that
    # progress (the next run skips already-translated rows), so the backfill
    # converges across runs instead of restarting from zero each time.
    rows = [{"id": f"e{i}", "title": f"제목{i}", "description": "", "tr": "", "lang": ""}
            for i in range(7)]
    repo = FakeRepo({"exh": rows})
    backfill_translations(repo, FakeTranslator(), flush_every=3)
    assert len(repo.patch_calls[SheetName.EXHIBITIONS]) == 3
    assert len(repo.patched[SheetName.EXHIBITIONS]) == 7


def test_stops_at_time_budget_and_flushes_progress():
    # The CI job has a fixed timeout; an unbounded backfill starves the later
    # export/commit steps (the web JSON never refreshes). A wall-clock budget
    # makes the backfill yield after flushing what it finished, so progress
    # persists and the run still exports. Here a fake clock advances 1s/row and
    # the 3s budget lets exactly 3 rows through before stopping.
    rows = [{"id": f"e{i}", "title": f"제목{i}", "description": "", "tr": "", "lang": ""}
            for i in range(10)]
    repo = FakeRepo({"exh": rows})
    clock = iter([0, 0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10])
    backfill_translations(repo, FakeTranslator(), flush_every=100,
                          max_seconds=3, now=lambda: next(clock))
    assert len(repo.patched[SheetName.EXHIBITIONS]) == 3


def test_venue_and_artist_names_are_translated():
    # 고유명사도 LLM 이 음역으로 잘 보존하므로 venue/artist name 도 번역 범위에 든다.
    repo = FakeRepo({
        "ven": [{"id": "v1", "name": "공근혜갤러리", "tr": "", "lang": ""}],
        "art": [{"id": "a1", "name": "戎康友", "tr": "", "lang": ""}],
    })
    backfill_translations(repo, FakeTranslator())
    v = json.loads({r["id"]: r for r in repo.patched[SheetName.VENUES]}["v1"]["tr"])
    assert v["en"]["name"] == "[en]공근혜갤러리"  # ko -> en
    assert v["ja"]["name"] == "[ja]공근혜갤러리"  # ko -> ja
    a = json.loads({r["id"]: r for r in repo.patched[SheetName.ARTISTS]}["a1"]["tr"])
    assert a["ko"]["name"] == "[ko]戎康友"        # ja -> ko


def test_prunes_out_of_scope_translations():
    # 범위에서 빠진 필드의 기존 번역은 재실행 시 제거된다 (자가 치유). 여기선 더는
    # 다루지 않는 "blurb" 필드. 범위 안 "name" 은 보존·보충된다.
    existing = json.dumps({"en": {"name": "[en]keep", "blurb": "stale"}})
    repo = FakeRepo({
        "ven": [{"id": "v1", "name": "공근혜갤러리", "tr": existing, "lang": "ko"}],
    })
    backfill_translations(repo, FakeTranslator())
    tr = json.loads({r["id"]: r for r in repo.patched[SheetName.VENUES]}["v1"]["tr"])
    assert "blurb" not in tr.get("en", {})        # out-of-scope field pruned
    assert tr["en"]["name"] == "[en]keep"          # in-scope kept (idempotent)
    assert tr["ja"]["name"] == "[ja]공근혜갤러리"   # missing locale filled
