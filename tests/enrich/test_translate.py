# tests/enrich/test_translate.py
import json

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
    def translate(self, text, from_code, to_code):
        return f"[{to_code}]{text}"


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
