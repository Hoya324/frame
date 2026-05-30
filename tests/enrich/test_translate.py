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

    def read_rows(self, sheet):
        return [dict(r) for r in self._rows[sheet]]

    def patch_rows(self, sheet, rows):
        self.patched[sheet] = rows

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


def test_venue_and_artist_fields():
    repo = FakeRepo({
        "ven": [{"id": "v1", "name": "BOOK AND SONS", "region": "世田谷", "district": "", "tr": "", "lang": ""}],
        "art": [{"id": "a1", "name": "戎康友", "tr": "", "lang": ""}],
    })
    backfill_translations(repo, FakeTranslator())
    v = repo.patched[SheetName.VENUES][0]
    vtr = json.loads(v["tr"])
    # name 은 라틴(en)으로 판정 -> en 제외, ko/ja 로 번역
    assert vtr["ko"]["name"] == "[ko]BOOK AND SONS"
    # region '世田谷' 은 ja 로 판정 -> ko/en 으로 번역
    assert vtr["ko"]["region"] == "[ko]世田谷"
    a = repo.patched[SheetName.ARTISTS][0]
    assert json.loads(a["tr"])["ko"]["name"] == "[ko]戎康友"
