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


def test_backfill_gives_up_after_consecutive_batch_failures():
    # When the daily request quota is exhausted every batch 429s. The backfill
    # must trip a circuit breaker and stop instead of hammering every remaining
    # row (which only burns the quota harder and wastes the run). The cleared/
    # unfilled rows are picked up by the next run once quota resets.
    def _err_429():
        req = httpx.Request("POST", "https://x/")
        resp = httpx.Response(429, request=req)
        return httpx.HTTPStatusError("rate limited", request=req, response=resp)

    class FailingTranslator:
        def __init__(self):
            self.calls = 0

        def translate(self, text, from_code, to_code):
            raise _err_429()

        def translate_batch(self, jobs):
            self.calls += 1
            raise _err_429()

    rows = [{"id": f"e{i}", "title": f"제목{i}", "description": "", "tr": "", "lang": ""}
            for i in range(100)]
    repo = FakeRepo({"exh": rows})
    t = FailingTranslator()
    report = backfill_translations(repo, t)
    assert t.calls <= 6                 # stopped early, didn't try all ~10 batches
    assert report.fields_translated == 0


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


def test_venue_and_artist_names_are_not_translated():
    # 고유명사(인명·기관명)는 오프라인 MT 가 엉뚱하게 번역하므로 아예 번역하지 않는다.
    repo = FakeRepo({
        "ven": [{"id": "v1", "name": "BOOK AND SONS", "tr": "", "lang": ""}],
        "art": [{"id": "a1", "name": "戎康友", "tr": "", "lang": ""}],
    })
    backfill_translations(repo, FakeTranslator())
    # 번역할 필드가 없으므로 patch 자체가 일어나지 않는다.
    assert SheetName.VENUES not in repo.patched
    assert SheetName.ARTISTS not in repo.patched


def test_prunes_out_of_scope_translations():
    # 범위에서 빠진 필드(여기선 name)의 기존 번역은 재실행 시 제거된다 — 과거
    # 오역 데이터를 번역 단계에서 자가 치유한다.
    existing = json.dumps({"ko": {"name": "[ko]오역"}, "en": {"name": "About Us"}})
    repo = FakeRepo({
        "ven": [{"id": "v1", "name": "공근혜갤러리", "tr": existing, "lang": "ja"}],
    })
    backfill_translations(repo, FakeTranslator())
    v = {r["id"]: r for r in repo.patched[SheetName.VENUES]}["v1"]
    assert v["tr"] == ""    # 남은 번역이 없으면 tr/lang 을 비운다
    assert v["lang"] == ""
