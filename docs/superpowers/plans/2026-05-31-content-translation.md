# 전시 콘텐츠 다국어 번역 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 크롤 시점에 Argos(오프라인)로 전시 제목·설명·미술관·작가명을 다른 로케일로 사전번역해 저장하고, 웹에서 원문 기본 표시 + 탭하면 현재 언어 번역(짧은 항목 인라인 토글 / 소개글 팝오버)을 보여준다.

**Architecture:** 파이썬 크롤러에 geocoder backfill과 동일한 패턴의 번역 enrich 스텝을 신설한다. 번역 결과는 sheet에 `lang`(원문 언어)·`tr`(JSON 직렬화된 `{locale: {field: text}}`) 컬럼으로 영속화되고, `json_export`가 catalog JSON에 `lang`/`tr`로 직렬화한다. 원문 언어는 스크립트 휴리스틱으로 필드별 판정한다. 웹은 `tr[currentLocale][field]`가 존재할 때만 번역 어포던스를 노출한다(원문 언어로 번역하지 않으므로 tr 존재 여부가 곧 "번역 가능" 신호). 기존 평면 `title_en`/`name_en`은 `tr.en`으로 일원화하며 제거한다.

**Tech Stack:** Python 3.12 / Pydantic / pytest, Argos Translate(오프라인 NMT). 웹: Next.js 16 / React 19 / TypeScript / Vitest + Testing Library.

---

## File Structure

**파이썬 (crawler)**
- Create `src/crawler/enrich/translator.py` — `Translator` 프로토콜 + `ArgosTranslator` 구현 + `detect_lang` 휴리스틱.
- Create `src/crawler/enrich/translate.py` — sheet 읽어 누락 `tr` 채우는 멱등 backfill (`backfill_translations`).
- Modify `src/crawler/cli.py` — `backfill-translations` 명령 + `_build_translator()`.
- Modify `src/crawler/sinks/json_export.py` — `tr`/`lang` 직렬화, `title_en`/`name_en` 방출 제거.
- Create `tests/enrich/test_translator.py`, `tests/enrich/test_translate.py`.
- Modify `tests/sinks/test_json_export.py`.
- Modify `pyproject.toml` — `argostranslate` 의존성.

**웹**
- Modify `web/src/lib/catalog.ts` — `tr`/`lang` 타입·파싱, `localized()` 헬퍼, `titleEn`/`nameEn` 제거.
- Modify `web/src/lib/i18n.ts` — 신규 라벨(`tr.machine`, `tr.showOriginal`, `tr.showTranslation`, `tr.close`).
- Create `web/src/components/TranslatableText.tsx` — 짧은 항목 인라인 토글.
- Create `web/src/components/TranslationPopover.tsx` — 소개글 팝오버.
- Modify `web/src/components/ExhibitionCard.tsx`, `web/src/components/ExhibitionDetailView.tsx`.
- Modify `web/src/test/lang.tsx` — `locale` 옵션 지원.
- Create `web/src/components/TranslatableText.test.tsx`, `web/src/components/TranslationPopover.test.tsx`.
- Modify `web/src/components/ExhibitionCard.test.tsx`.

---

## Phase A — Crawler 번역 파이프라인 (Python)

### Task 1: Translator 프로토콜 + 언어 판정 휴리스틱

**Files:**
- Create: `src/crawler/enrich/translator.py`
- Test: `tests/enrich/test_translator.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/enrich/test_translator.py
from crawler.enrich.translator import detect_lang, TARGET_LOCALES, targets_for


def test_detect_lang_hangul():
    assert detect_lang("을지로의 밤") == "ko"


def test_detect_lang_kana_or_han():
    assert detect_lang("カリフォルニア") == "ja"
    assert detect_lang("世田谷") == "ja"  # 한자만 있어도 일본어로 본다 (한국어는 한글 사용)


def test_detect_lang_latin_fallback():
    assert detect_lang("BOOK AND SONS") == "en"


def test_targets_excludes_source():
    assert set(targets_for("ko")) == {"en", "ja"}
    assert set(targets_for("ja")) == {"en", "ko"}
    assert set(TARGET_LOCALES) == {"ko", "en", "ja"}
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/enrich/test_translator.py -v`
Expected: FAIL — `ModuleNotFoundError: crawler.enrich.translator`

- [ ] **Step 3: Write minimal implementation**

```python
# src/crawler/enrich/translator.py
"""Offline translation (Argos) plus source-language detection by script."""

from __future__ import annotations

import logging
import re
from typing import Protocol

logger = logging.getLogger(__name__)

TARGET_LOCALES: tuple[str, ...] = ("ko", "en", "ja")

_HANGUL = re.compile(r"[가-힣]")
_KANA = re.compile(r"[぀-ヿ]")
_HAN = re.compile(r"[一-鿿]")


def detect_lang(text: str) -> str:
    """Best-effort source language for our two CJK + latin world.

    Hangul -> ko. Kana or bare Han -> ja (Korean uses hangul, not bare hanja,
    so Han-only strings like '世田谷' are treated as Japanese). Else -> en.
    """
    if _HANGUL.search(text):
        return "ko"
    if _KANA.search(text) or _HAN.search(text):
        return "ja"
    return "en"


def targets_for(source_lang: str) -> list[str]:
    """Locales we translate INTO — every supported locale except the source."""
    return [loc for loc in TARGET_LOCALES if loc != source_lang]


class Translator(Protocol):
    def translate(self, text: str, from_code: str, to_code: str) -> str: ...
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/enrich/test_translator.py -v`
Expected: PASS (4 passed)

- [ ] **Step 5: Commit**

```bash
git add src/crawler/enrich/translator.py tests/enrich/test_translator.py
git commit -m "feat(crawler): add language detection + Translator protocol"
```

---

### Task 2: ArgosTranslator 구현 + 의존성

**Files:**
- Modify: `src/crawler/enrich/translator.py`
- Modify: `pyproject.toml` (dependencies)
- Test: `tests/enrich/test_translator.py`

- [ ] **Step 1: Write the failing test**

`ArgosTranslator`는 모델 설치/추론을 래핑한다. argostranslate 라이브러리는 테스트에서 모킹한다.

```python
# tests/enrich/test_translator.py  (추가)
from unittest.mock import MagicMock
import sys
import types


def _install_fake_argos(monkeypatch):
    pkg = types.ModuleType("argostranslate.package")
    trans = types.ModuleType("argostranslate.translate")
    pkg.get_installed_packages = MagicMock(return_value=[])
    pkg.get_available_packages = MagicMock(return_value=[])
    pkg.update_package_index = MagicMock()
    trans.translate = MagicMock(side_effect=lambda text, frm, to: f"[{to}]{text}")
    root = types.ModuleType("argostranslate")
    monkeypatch.setitem(sys.modules, "argostranslate", root)
    monkeypatch.setitem(sys.modules, "argostranslate.package", pkg)
    monkeypatch.setitem(sys.modules, "argostranslate.translate", trans)
    return pkg, trans


def test_argos_translator_delegates(monkeypatch):
    from crawler.enrich.translator import ArgosTranslator

    _pkg, trans = _install_fake_argos(monkeypatch)
    t = ArgosTranslator()
    assert t.translate("hello", "en", "ko") == "[ko]hello"
    trans.translate.assert_called_once_with("hello", "en", "ko")


def test_argos_translator_blank_passthrough(monkeypatch):
    from crawler.enrich.translator import ArgosTranslator

    _install_fake_argos(monkeypatch)
    t = ArgosTranslator()
    assert t.translate("   ", "en", "ko") == "   "
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/enrich/test_translator.py -v`
Expected: FAIL — `ImportError: cannot import name 'ArgosTranslator'`

- [ ] **Step 3: Write minimal implementation**

`src/crawler/enrich/translator.py` 끝에 추가:

```python
class ArgosTranslator:
    """Argos Translate wrapper. Installs missing language-pair packages on
    first use, then delegates to argostranslate's auto-pivoting translate()."""

    def __init__(self) -> None:
        self._ensured: set[tuple[str, str]] = set()

    def _ensure_pair(self, from_code: str, to_code: str) -> None:
        if (from_code, to_code) in self._ensured:
            return
        import argostranslate.package as pkg

        installed = {
            (p.from_code, p.to_code) for p in pkg.get_installed_packages()
        }
        if (from_code, to_code) not in installed:
            try:
                pkg.update_package_index()
                available = pkg.get_available_packages()
                match = next(
                    (
                        p
                        for p in available
                        if p.from_code == from_code and p.to_code == to_code
                    ),
                    None,
                )
                if match is not None:
                    match.install()
            except Exception:
                logger.exception(
                    "argos: failed to install %s->%s package", from_code, to_code
                )
        self._ensured.add((from_code, to_code))

    def translate(self, text: str, from_code: str, to_code: str) -> str:
        if not text or not text.strip():
            return text
        import argostranslate.translate as tr

        self._ensure_pair(from_code, to_code)
        return tr.translate(text, from_code, to_code)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/enrich/test_translator.py -v`
Expected: PASS (6 passed)

- [ ] **Step 5: Add dependency**

`pyproject.toml`의 `[project] dependencies` 리스트에 한 줄 추가 (기존 줄들과 같은 들여쓰기):

```toml
  "argostranslate>=1.9,<2",
```

- [ ] **Step 6: Commit**

```bash
git add src/crawler/enrich/translator.py tests/enrich/test_translator.py pyproject.toml
git commit -m "feat(crawler): add ArgosTranslator offline translation wrapper"
```

---

### Task 3: 번역 backfill enrich 스텝 (멱등)

**Files:**
- Create: `src/crawler/enrich/translate.py`
- Test: `tests/enrich/test_translate.py`

이 스텝은 geocoder backfill과 동일한 형태(`read_rows` → `patch_rows`)다. 각 sheet의 번역 대상 필드를 읽어, 원문 외 로케일에 대해 누락된 항목만 채운 `tr`(JSON 문자열)과 `lang` 컬럼을 patch한다.

번역 대상 필드:
- Exhibitions: `title`, `description`
- Venues: `name`, `region`, `district`
- Artists: `name`

- [ ] **Step 1: Write the failing test**

```python
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/enrich/test_translate.py -v`
Expected: FAIL — `ModuleNotFoundError: crawler.enrich.translate`

- [ ] **Step 3: Write minimal implementation**

```python
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
    SheetName.VENUES: ("name", "region", "district"),
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
    repo: Repository, sheet: SheetName, fields: tuple[str, ...], translator: Translator
) -> tuple[int, int, int, int]:
    rows = repo.read_rows(sheet)
    patches: list[dict] = []
    fields_translated = 0
    errors = 0

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
            patches.append({
                "id": row["id"],
                "tr": json.dumps(existing, ensure_ascii=False),
                "lang": _row_lang(row, fields),
            })

    if patches:
        repo.patch_rows(sheet, patches)
    return len(rows), len(patches), fields_translated, errors


def backfill_translations(repo: Repository, translator: Translator) -> TranslationReport:
    seen = patched = translated = errors = 0
    for sheet, fields in _FIELDS.items():
        s, p, t, e = _backfill_sheet(repo, sheet, fields, translator)
        seen += s
        patched += p
        translated += t
        errors += e
    return TranslationReport(seen, patched, translated, errors)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/enrich/test_translate.py -v`
Expected: PASS (4 passed)

- [ ] **Step 5: Commit**

```bash
git add src/crawler/enrich/translate.py tests/enrich/test_translate.py
git commit -m "feat(crawler): add idempotent translation backfill enrich step"
```

---

### Task 4: CLI `backfill-translations` 명령

**Files:**
- Modify: `src/crawler/cli.py`
- Test: `tests/test_cli.py`

- [ ] **Step 1: Read the existing CLI backfill command for the exact pattern**

Run: `sed -n '195,230p' src/crawler/cli.py`
기존 `backfill-geocodes` 명령(`@app.command("backfill-geocodes")`)과 `_open_repo()`/로그 패턴을 그대로 따른다.

- [ ] **Step 2: Write the failing test**

```python
# tests/test_cli.py  (추가)
def test_backfill_translations_invokes_backfill(monkeypatch):
    import crawler.cli as cli
    from crawler.enrich.translate import TranslationReport

    calls = {}

    def fake_backfill(repo, translator):
        calls["called"] = True
        return TranslationReport(rows_seen=3, rows_patched=1, fields_translated=2, errors=0)

    monkeypatch.setattr(cli, "_open_repo", lambda: object())
    monkeypatch.setattr(cli, "_build_translator", lambda: object(), raising=False)
    monkeypatch.setattr("crawler.enrich.translate.backfill_translations", fake_backfill)

    cli.backfill_translations_cmd()
    assert calls["called"] is True
```

해당 테스트의 `_open_repo` 이름이 다르면 Step 1에서 확인한 실제 헬퍼명으로 맞춘다.

- [ ] **Step 3: Run test to verify it fails**

Run: `pytest tests/test_cli.py::test_backfill_translations_invokes_backfill -v`
Expected: FAIL — `AttributeError: module 'crawler.cli' has no attribute 'backfill_translations_cmd'`

- [ ] **Step 4: Write minimal implementation**

`src/crawler/cli.py`에 추가 (기존 `backfill_geocodes_cmd` 바로 아래, 같은 import 스타일):

```python
def _build_translator():
    from crawler.enrich.translator import ArgosTranslator

    return ArgosTranslator()


@app.command("backfill-translations")
def backfill_translations_cmd() -> None:
    """Translate exhibition/venue/artist text into the other locales (one-time + incremental)."""
    from crawler.enrich.translate import backfill_translations

    repo = _open_repo()
    translator = _build_translator()
    report = backfill_translations(repo, translator)
    log.info(
        "translations: seen=%s, patched=%s, fields=%s, errors=%s",
        report.rows_seen, report.rows_patched, report.fields_translated, report.errors,
    )
```

`_open_repo`/`log`의 실제 식별자는 Step 1에서 확인한 것으로 맞춘다.

- [ ] **Step 5: Run test to verify it passes**

Run: `pytest tests/test_cli.py::test_backfill_translations_invokes_backfill -v`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add src/crawler/cli.py tests/test_cli.py
git commit -m "feat(crawler): add backfill-translations CLI command"
```

---

### Task 5: json_export — `tr`/`lang` 직렬화 + `title_en`/`name_en` 제거

**Files:**
- Modify: `src/crawler/sinks/json_export.py`
- Test: `tests/sinks/test_json_export.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/sinks/test_json_export.py  (추가)
import json as _json
from crawler.sinks.json_export import _exhibition_json, _venue_full, _artist_full, _venue_embed


def test_exhibition_json_emits_tr_and_lang_no_title_en():
    row = {
        "id": "e1", "title": "戎康友 展",
        "lang": "ja",
        "tr": _json.dumps({"ko": {"title": "에비스 전", "description": "캘리포니아"}}),
        "venue_id": "", "artist_ids": "",
    }
    out = _exhibition_json(row, {}, {})
    assert out["lang"] == "ja"
    assert out["tr"]["ko"]["title"] == "에비스 전"
    assert "title_en" not in out


def test_venue_and_artist_emit_tr_no_name_en():
    v = _venue_full({"id": "v1", "name": "BOOK AND SONS",
                     "lang": "en", "tr": _json.dumps({"ko": {"name": "북앤선즈"}})})
    assert v["tr"]["ko"]["name"] == "북앤선즈"
    assert "name_en" not in v
    a = _artist_full({"id": "a1", "name": "戎康友",
                      "lang": "ja", "tr": _json.dumps({"ko": {"name": "에비스"}})})
    assert a["tr"]["ko"]["name"] == "에비스"
    assert "name_en" not in a


def test_tr_defaults_to_empty_dict_when_missing():
    out = _exhibition_json({"id": "e1", "title": "x", "venue_id": "", "artist_ids": ""}, {}, {})
    assert out["tr"] == {}
    assert out["lang"] is None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/sinks/test_json_export.py -v`
Expected: FAIL — `KeyError: 'tr'` / `assert 'title_en' not in out` 실패

- [ ] **Step 3: Write minimal implementation**

`json_export.py` 상단(다른 `_*_or_none` 헬퍼 근처)에 추가:

```python
def _tr(value: object) -> dict:
    """Parse the stored ``tr`` JSON column into a nested {locale:{field:text}} dict."""
    if not value:
        return {}
    try:
        parsed = json.loads(value) if isinstance(value, str) else value
    except (ValueError, TypeError):
        return {}
    return parsed if isinstance(parsed, dict) else {}
```

`_exhibition_json`에서 `"title_en": _str_or_none(row.get("title_en")),` 줄을 삭제하고 대신 추가:

```python
        "lang": _str_or_none(row.get("lang")),
        "tr": _tr(row.get("tr")),
```

`_venue_full`에서 `"name_en": _str_or_none(row.get("name_en")),` 줄을 삭제하고 추가:

```python
        "lang": _str_or_none(row.get("lang")),
        "tr": _tr(row.get("tr")),
```

`_artist_full`에서 `"name_en": _str_or_none(row.get("name_en")),` 줄을 삭제하고 추가:

```python
        "lang": _str_or_none(row.get("lang")),
        "tr": _tr(row.get("tr")),
```

`_venue_embed`(전시 카드/상세에 박히는 축약형)에도 번역이 필요하므로 추가:

```python
        "lang": _str_or_none(row.get("lang")),
        "tr": _tr(row.get("tr")),
```

`_exhibition_json`의 `"artists": [...]` 항목도 임베드 번역을 싣도록 교체:

```python
        "artists": [
            {
                "id": _id(artists[aid]["id"]),
                "name": artists[aid]["name"],
                "tr": _tr(artists[aid].get("tr")),
            }
            for aid in artist_ids
            if aid in artists
        ],
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/sinks/test_json_export.py -v`
Expected: PASS

- [ ] **Step 5: Run the full python suite + lint**

Run: `pytest -q && ruff check src tests`
Expected: PASS, no lint errors. (기존 export 테스트 중 `title_en`/`name_en`을 단언하던 것이 있으면 `tr` 기반으로 수정한다.)

- [ ] **Step 6: Commit**

```bash
git add src/crawler/sinks/json_export.py tests/sinks/test_json_export.py
git commit -m "feat(crawler): export tr/lang and drop flat title_en/name_en"
```

---

## Phase B — 웹 표시 & 인터랙션

### Task 6: catalog 타입·파싱 — `tr`/`lang`, `localized()` 헬퍼, `titleEn`/`nameEn` 제거

**Files:**
- Modify: `web/src/lib/catalog.ts`
- Test: `web/src/lib/catalog.test.ts` (Create)

- [ ] **Step 1: Write the failing test**

```ts
// web/src/lib/catalog.test.ts
import { describe, expect, it } from "vitest";
import { parseCatalog, localized } from "@/lib/catalog";

const raw = {
  generated_at: "2026-05-31T00:00:00Z",
  exhibitions: [{
    id: "e1", title: "戎康友 展", lang: "ja",
    tr: { ko: { title: "에비스 전", description: "캘리포니아" } },
    description: "カリフォルニア",
    venue: { id: "v1", name: "BOOK AND SONS", lang: "en", tr: { ko: { name: "북앤선즈" } } },
    artists: [{ id: "a1", name: "戎康友", tr: { ko: { name: "에비스" } } }],
  }],
  venues: [], artists: [],
};

describe("parseCatalog tr/lang", () => {
  it("parses tr and lang onto exhibition, venue, artist", () => {
    const c = parseCatalog(raw);
    const e = c.exhibitions[0];
    expect(e.lang).toBe("ja");
    expect(e.tr.ko?.title).toBe("에비스 전");
    expect(e.venue?.tr.ko?.name).toBe("북앤선즈");
    expect(e.artists[0].tr.ko?.name).toBe("에비스");
  });
});

describe("localized", () => {
  it("returns translation when present for locale", () => {
    expect(localized("戎康友 展", { ko: { title: "에비스 전" } }, "ko", "title")).toBe("에비스 전");
  });
  it("returns null when no translation for locale (treat as original)", () => {
    expect(localized("을지로의 밤", {}, "ko", "title")).toBeNull();
    expect(localized("戎康友 展", { ko: { title: "에비스 전" } }, "ja", "title")).toBeNull();
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd web && npx vitest run src/lib/catalog.test.ts`
Expected: FAIL — `localized` export 없음 / `tr` 타입 없음

- [ ] **Step 3: Write minimal implementation**

`web/src/lib/catalog.ts` 수정. 상단에 타입 추가하고 인터페이스/파서를 갱신한다.

```ts
import type { Locale } from "@/lib/i18n";

// 번역 맵: 로케일 -> 필드 -> 번역 텍스트. 원문 언어 키는 들어있지 않다.
export type TrMap = Partial<Record<Locale, Record<string, string>>>;
```

`VenueEmbed`, `Exhibition`, 임베드 artist, 그리고 `Venue`/top-level artist에 `lang`/`tr`를 추가하고 `titleEn`/`nameEn`을 제거한다:

```ts
export interface VenueEmbed {
  id: string; name: string; region: string | null; district: string | null;
  lat: number | null; lng: number | null;
  lang: string | null; tr: TrMap;
}
export interface Exhibition {
  id: string; title: string;
  posterImageUrl: string | null; description: string | null;
  medium: string | null; exhibitionType: string | null; genreTags: string[];
  feeType: string | null; priceMin: number | null; priceMax: number | null;
  startDate: string | null; endDate: string | null;
  status: Status; openHours: string | null;
  venue: VenueEmbed | null;
  artists: { id: string; name: string; tr: TrMap }[];
  sourceUrl: string | null; featured: boolean; popularityScore: number | null;
  lang: string | null; tr: TrMap;
}
export interface Venue {
  id: string; name: string; venueType: string | null;
  region: string | null; district: string | null; address: string | null;
  country: string | null; lat: number | null; lng: number | null; website: string | null;
  lang: string | null; tr: TrMap;
}
export interface Catalog {
  generatedAt: string;
  exhibitions: Exhibition[];
  venues: Venue[];
  artists: { id: string; name: string; tr: TrMap }[];
}
```

`parseCatalog` 내부 매핑을 갱신한다(추가/삭제만 표시):

```ts
// helper near top of file
function trOf(v: any): TrMap {
  return v && typeof v === "object" ? (v as TrMap) : {};
}
```

- exhibition 매핑: `title_en` 줄 제거, `lang: e.lang ?? null, tr: trOf(e.tr),` 추가. `artists: e.artists ?? []` 를 아래로 교체:
  ```ts
  artists: (e.artists ?? []).map((a: any) => ({ id: a.id, name: a.name, tr: trOf(a.tr) })),
  ```
- venue embed 매핑에 `lang: e.venue.lang ?? null, tr: trOf(e.venue.tr),` 추가.
- venues 매핑: `name_en` 줄 제거, `lang: v.lang ?? null, tr: trOf(v.tr),` 추가.
- artists 매핑: `name_en` 줄 제거, `tr: trOf(a.tr)` 추가.

파일 끝에 헬퍼 추가:

```ts
// 현재 로케일에 번역이 있으면 그 텍스트, 없으면 null(=원문 그대로 써야 함).
export function localized(
  original: string | null | undefined,
  tr: TrMap | undefined,
  locale: Locale,
  field: string,
): string | null {
  const text = tr?.[locale]?.[field];
  if (!text) return null;
  if (text === (original ?? "")) return null;
  return text;
}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd web && npx vitest run src/lib/catalog.test.ts`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add web/src/lib/catalog.ts web/src/lib/catalog.test.ts
git commit -m "feat(web): parse tr/lang and add localized() helper"
```

---

### Task 7: i18n 신규 라벨 + 테스트용 locale 주입

**Files:**
- Modify: `web/src/lib/i18n.ts`
- Modify: `web/src/test/lang.tsx`

- [ ] **Step 1: Add i18n labels**

`i18n.ts`의 `ko`/`en`/`ja` 딕셔너리 각각에 키 추가:

```ts
// ko
"tr.machine": "기계번역",
"tr.showTranslation": "번역",
"tr.showOriginal": "원문",
"tr.close": "닫기",
// en
"tr.machine": "Machine translation",
"tr.showTranslation": "Translate",
"tr.showOriginal": "Original",
"tr.close": "Close",
// ja
"tr.machine": "機械翻訳",
"tr.showTranslation": "翻訳",
"tr.showOriginal": "原文",
"tr.close": "閉じる",
```

- [ ] **Step 2: Extend renderWithLang to seed a locale**

`web/src/test/lang.tsx`를 교체:

```tsx
import { render, type RenderOptions } from "@testing-library/react";
import { LanguageProvider } from "@/components/LanguageProvider";
import type { ReactElement } from "react";
import type { Locale } from "@/lib/i18n";

// LanguageProvider reads the persisted locale on mount; seed it for tests.
export function renderWithLang(
  ui: ReactElement,
  options?: RenderOptions & { locale?: Locale },
) {
  if (options?.locale) {
    window.localStorage.setItem("frame.locale", options.locale);
  } else {
    window.localStorage.removeItem("frame.locale");
  }
  return render(ui, {
    wrapper: ({ children }) => <LanguageProvider>{children}</LanguageProvider>,
    ...options,
  });
}
```

(STORAGE_KEY 값은 `LanguageProvider.tsx`의 `const STORAGE_KEY = "frame.locale"`와 일치해야 한다 — 다르면 그 값으로 맞춘다.)

- [ ] **Step 3: Run existing tests to confirm no regression**

Run: `cd web && npx vitest run src/components/ExhibitionCard.test.tsx`
Expected: PASS (기존 카드 테스트는 ko 기본이라 영향 없음 — 단, Task 9에서 카드의 titleEn 제거 반영 전이므로 여기선 ExhibitionCard 미수정 상태. 이 스텝은 lang 헬퍼만 검증)

만약 이 시점에 `ExhibitionCard`가 아직 `e.titleEn`을 참조해 타입 에러가 나면, 그건 Task 6에서 `titleEn`을 제거했기 때문이다. → Task 9에서 카드를 고치므로, 그 전까지 컴파일을 위해 Task 9를 곧바로 이어서 진행한다. (순서상 6→7→9 권장)

- [ ] **Step 4: Commit**

```bash
git add web/src/lib/i18n.ts web/src/test/lang.tsx
git commit -m "feat(web): add translation ui labels and test locale seeding"
```

---

### Task 8: `TranslatableText` (짧은 항목 인라인 토글)

**Files:**
- Create: `web/src/components/TranslatableText.tsx`
- Test: `web/src/components/TranslatableText.test.tsx`

동작: 현재 로케일 번역이 있으면 점선 밑줄 + 작은 칩을 보여주고, 클릭하면 번역↔원문 토글. 번역이 없으면 원문을 순수 텍스트로 렌더(어포던스 없음).

- [ ] **Step 1: Write the failing test**

```tsx
// web/src/components/TranslatableText.test.tsx
import { screen, fireEvent } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { renderWithLang } from "@/test/lang";
import { TranslatableText } from "@/components/TranslatableText";

describe("TranslatableText", () => {
  it("shows original by default and toggles to translation on click (ko locale)", () => {
    renderWithLang(
      <TranslatableText original="戎康友 展" tr={{ ko: { title: "에비스 전" } }} field="title" />,
      { locale: "ko" },
    );
    // 기본 = 원문
    expect(screen.getByText("戎康友 展")).toBeInTheDocument();
    // 칩 클릭 -> 번역
    fireEvent.click(screen.getByRole("button"));
    expect(screen.getByText("에비스 전")).toBeInTheDocument();
    // 다시 클릭 -> 원문 복귀
    fireEvent.click(screen.getByRole("button"));
    expect(screen.getByText("戎康友 展")).toBeInTheDocument();
  });

  it("renders plain original with no button when no translation for locale", () => {
    renderWithLang(
      <TranslatableText original="을지로의 밤" tr={{}} field="title" />,
      { locale: "ko" },
    );
    expect(screen.getByText("을지로의 밤")).toBeInTheDocument();
    expect(screen.queryByRole("button")).toBeNull();
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd web && npx vitest run src/components/TranslatableText.test.tsx`
Expected: FAIL — 모듈 없음

- [ ] **Step 3: Write minimal implementation**

```tsx
// web/src/components/TranslatableText.tsx
"use client";
import { useState } from "react";
import { useLang } from "@/components/LanguageProvider";
import { localized, type TrMap } from "@/lib/catalog";

export function TranslatableText({
  original, tr, field, className,
}: {
  original: string | null | undefined;
  tr: TrMap | undefined;
  field: string;
  className?: string;
}) {
  const { locale, t } = useLang();
  const [showTr, setShowTr] = useState(false);
  const translation = localized(original, tr, locale, field);
  const text = original ?? "";

  if (!translation) return <span className={className}>{text}</span>;

  return (
    <span className={className}>
      <span className="border-b border-dotted border-tx3">
        {showTr ? translation : text}
      </span>
      <button
        type="button"
        onClick={(e) => { e.preventDefault(); e.stopPropagation(); setShowTr((v) => !v); }}
        className="ml-1.5 rounded-full border border-line2 px-1.5 py-0.5 align-middle text-[9.5px] text-tx3 hover:bg-panel2"
      >
        {showTr ? t("tr.showOriginal") : t("tr.showTranslation")}
      </button>
    </span>
  );
}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd web && npx vitest run src/components/TranslatableText.test.tsx`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add web/src/components/TranslatableText.tsx web/src/components/TranslatableText.test.tsx
git commit -m "feat(web): add TranslatableText inline toggle component"
```

---

### Task 9: `ExhibitionCard` 연결 (제목·장소) + titleEn 제거

**Files:**
- Modify: `web/src/components/ExhibitionCard.tsx`
- Modify: `web/src/components/ExhibitionCard.test.tsx`

- [ ] **Step 1: Update the test**

`ExhibitionCard.test.tsx`의 fixture `E`에서 `titleEn: null,`을 제거하고, 다음을 추가한다: exhibition에 `lang: null, tr: {},`, venue에 `lang: null, tr: {},`. 그리고 번역 토글 케이스를 한 개 추가:

```tsx
it("offers translation toggle when tr exists for current locale", () => {
  const JP: Exhibition = {
    ...E, id: "e2", title: "戎康友 展", lang: "ja",
    tr: { ko: { title: "에비스 전" } },
    venue: { ...E.venue!, name: "BOOK AND SONS", lang: "en", tr: { ko: { name: "북앤선즈" } } },
  };
  renderWithLang(<ExhibitionCard exhibition={JP} today={new Date("2026-05-30T00:00:00+09:00")} />, { locale: "ko" });
  expect(screen.getByText("戎康友 展")).toBeInTheDocument();          // 기본 원문
  fireEvent.click(screen.getAllByRole("button")[0]);                 // 첫 칩(제목) 토글
  expect(screen.getByText("에비스 전")).toBeInTheDocument();
});
```

상단 import에 `fireEvent` 추가: `import { screen, fireEvent } from "@testing-library/react";`

- [ ] **Step 2: Run test to verify it fails**

Run: `cd web && npx vitest run src/components/ExhibitionCard.test.tsx`
Expected: FAIL — 카드가 아직 `bilingual(e.title, e.titleEn)`를 사용(타입 에러/토글 없음)

- [ ] **Step 3: Update the component**

`ExhibitionCard.tsx`:
- import 교체: `import { bilingual } from "@/lib/i18n";` 제거, `import { TranslatableText } from "@/components/TranslatableText";` 추가.
- `const title = bilingual(e.title, e.titleEn);` 줄 제거.
- 제목 렌더 교체:
  ```tsx
  <div className="text-[14.5px] font-semibold leading-tight">
    <TranslatableText original={e.title} tr={e.tr} field="title" />
  </div>
  ```
- 장소 렌더 교체(기존 `${e.venue.name}...` 부분):
  ```tsx
  <div className="mt-1 text-[12.5px] text-tx2">
    {e.venue ? (
      <>
        <TranslatableText original={e.venue.name} tr={e.venue.tr} field="name" />
        {e.venue.district ? ` · ${e.venue.district}` : ""}
      </>
    ) : t("common.venueTbd")}
  </div>
  ```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd web && npx vitest run src/components/ExhibitionCard.test.tsx`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add web/src/components/ExhibitionCard.tsx web/src/components/ExhibitionCard.test.tsx
git commit -m "feat(web): wire TranslatableText into ExhibitionCard"
```

---

### Task 10: `TranslationPopover` (소개글) + 상세 화면 연결

**Files:**
- Create: `web/src/components/TranslationPopover.tsx`
- Create: `web/src/components/TranslationPopover.test.tsx`
- Modify: `web/src/components/ExhibitionDetailView.tsx`

- [ ] **Step 1: Write the failing test**

```tsx
// web/src/components/TranslationPopover.test.tsx
import { screen, fireEvent } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { renderWithLang } from "@/test/lang";
import { TranslationPopover } from "@/components/TranslationPopover";

describe("TranslationPopover", () => {
  it("renders original, opens popover with translation, and closes it", () => {
    renderWithLang(
      <TranslationPopover original="カリフォルニア…" tr={{ ko: { description: "캘리포니아…" } }} field="description" />,
      { locale: "ko" },
    );
    expect(screen.getByText("カリフォルニア…")).toBeInTheDocument();
    expect(screen.queryByText("캘리포니아…")).toBeNull();   // 닫힌 상태

    fireEvent.click(screen.getByRole("button", { name: /번역/ }));
    expect(screen.getByText("캘리포니아…")).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: /닫기/ }));
    expect(screen.queryByText("캘리포니아…")).toBeNull();
  });

  it("renders plain text with no trigger when no translation", () => {
    renderWithLang(
      <TranslationPopover original="국문 소개" tr={{}} field="description" />,
      { locale: "ko" },
    );
    expect(screen.getByText("국문 소개")).toBeInTheDocument();
    expect(screen.queryByRole("button")).toBeNull();
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd web && npx vitest run src/components/TranslationPopover.test.tsx`
Expected: FAIL — 모듈 없음

- [ ] **Step 3: Write minimal implementation**

```tsx
// web/src/components/TranslationPopover.tsx
"use client";
import { useState } from "react";
import { useLang } from "@/components/LanguageProvider";
import { localized, type TrMap } from "@/lib/catalog";

export function TranslationPopover({
  original, tr, field, className,
}: {
  original: string | null | undefined;
  tr: TrMap | undefined;
  field: string;
  className?: string;
}) {
  const { locale, t } = useLang();
  const [open, setOpen] = useState(false);
  const translation = localized(original, tr, locale, field);
  const text = original ?? "";

  if (!translation) return <p className={className}>{text}</p>;

  return (
    <div className="relative">
      <p className={className}>{text}</p>
      <button
        type="button"
        onClick={() => setOpen(true)}
        className="mt-2 rounded-full border border-line2 px-2.5 py-1 text-[11px] text-tx3 hover:bg-panel2"
      >
        {t("tr.showTranslation")}
      </button>
      {open && (
        <div className="mt-2 rounded-lg border border-line bg-panel p-3 shadow-lg">
          <div className="mb-1.5 flex items-center justify-between text-[10px] text-tx3">
            <span>{t("tr.machine")}</span>
            <button type="button" aria-label={t("tr.close")} onClick={() => setOpen(false)}>✕</button>
          </div>
          <p className="whitespace-pre-line text-[13px] leading-relaxed">{translation}</p>
        </div>
      )}
    </div>
  );
}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd web && npx vitest run src/components/TranslationPopover.test.tsx`
Expected: PASS

- [ ] **Step 5: Wire into ExhibitionDetailView**

`ExhibitionDetailView.tsx`:
- import 추가: `import { TranslatableText } from "@/components/TranslatableText";` 와 `import { TranslationPopover } from "@/components/TranslationPopover";`
- 제목(`<h1 ...>{e.title}</h1>` 와 그 아래 `{e.titleEn && ...}` 두 줄) 교체:
  ```tsx
  <h1 className="mt-3 text-3xl font-extrabold tracking-tight">
    <TranslatableText original={e.title} tr={e.tr} field="title" />
  </h1>
  ```
  (기존 `{e.titleEn && <div ...>{e.titleEn}</div>}` 줄은 제거 — `titleEn`은 더 이상 존재하지 않음)
- 장소 줄의 `{e.venue?.name ?? t("common.tbd")}` 를 교체:
  ```tsx
  {e.venue ? <TranslatableText original={e.venue.name} tr={e.venue.tr} field="name" /> : t("common.tbd")}
  ```
- 작가 줄 `{e.artists.map((a) => a.name).join(", ")}` 를 교체(작가별 토글):
  ```tsx
  {e.artists.map((a, i) => (
    <span key={a.id}>
      {i > 0 ? ", " : ""}
      <TranslatableText original={a.name} tr={a.tr} field="name" />
    </span>
  ))}
  ```
- 소개글 `{e.description && <p ...>{e.description}</p>}` 교체:
  ```tsx
  {e.description && (
    <TranslationPopover
      original={e.description}
      tr={e.tr}
      field="description"
      className="mt-6 whitespace-pre-line text-[14px] leading-relaxed text-tx2"
    />
  )}
  ```

- [ ] **Step 6: Run web test suite + typecheck + lint**

Run: `cd web && npx vitest run && npx tsc --noEmit && npm run lint`
Expected: 전부 PASS, 타입 에러 0 (`titleEn`/`nameEn` 잔존 참조가 있으면 여기서 드러난다 — 모두 제거).

- [ ] **Step 7: Commit**

```bash
git add web/src/components/TranslationPopover.tsx web/src/components/TranslationPopover.test.tsx web/src/components/ExhibitionDetailView.tsx
git commit -m "feat(web): add TranslationPopover and wire detail view translations"
```

---

### Task 11: 데이터 백필 실행 + 검증

**Files:**
- 데이터: `web/public/data/exhibitions.json` (재생성/갱신)

이 태스크는 코드가 아니라 1회성 백필 실행이다. 실제 store(시트)에 접근 가능한 환경에서 수행한다.

- [ ] **Step 1: Install Argos models cache (first run downloads packages)**

Run: `python -c "import argostranslate.package as p; p.update_package_index()"`
Expected: 에러 없이 종료(인덱스 갱신).

- [ ] **Step 2: Run the backfill**

Run: 프로젝트 CLI로 `backfill-translations` 실행 (예: `python -m crawler.cli backfill-translations` — 실제 엔트리포인트는 `cli.py`의 `app` 등록명에 맞춘다).
Expected: 로그에 `translations: seen=..., patched=..., fields=..., errors=0` 출력. errors가 0이 아니면 로그를 확인.

- [ ] **Step 3: Re-export the catalog JSON**

Run: 기존 export 경로(`write_catalog`)로 `web/public/data/exhibitions.json` 재생성하는 프로젝트 명령 실행.
Expected: 종료 코드 0.

- [ ] **Step 4: Verify output shape**

Run:
```bash
python3 -c "
import json
d=json.load(open('web/public/data/exhibitions.json'))
ja=[e for e in d['exhibitions'] if (e.get('lang')=='ja')]
print('ja exhibitions:', len(ja))
sample=next((e for e in ja if e.get('tr',{}).get('ko',{}).get('title')), None)
print('sample ko title:', sample and sample['tr']['ko']['title'])
assert all('title_en' not in e for e in d['exhibitions']), 'title_en leaked'
print('ok')
"
```
Expected: `ja exhibitions: N(>0)`, 샘플 ko 제목 출력, `ok`.

- [ ] **Step 5: Commit data**

```bash
git add web/public/data/exhibitions.json
git commit -m "chore(data): backfill translations into catalog"
```

---

### Task 12: 수동 UI 검증 (golden path)

- [ ] **Step 1: Run the web dev server**

Run: `cd web && npm run dev`
브라우저에서 일본 소스 전시 상세 페이지를 연다.

- [ ] **Step 2: Verify interactions**

- 기본 = 원문(일본어) 표시, 제목·장소·작가에 점선+칩 노출.
- 제목 칩 클릭 → 한국어 번역으로 토글, 다시 클릭 → 원문 복귀.
- 소개글 "번역" 버튼 → 팝오버에 한국어 번역 + "기계번역" 라벨, ✕로 닫힘.
- 언어 스위처를 en으로 바꾸면 동일 항목이 영어 번역으로 토글되는지 확인.
- 한국어 소스 전시(원문이 한국어)는 ko 모드에서 칩이 안 보이고, ja/en 모드에서 칩이 보이는지 확인.

- [ ] **Step 3: Run full suites once more**

Run: `pytest -q && cd web && npx vitest run && npx tsc --noEmit`
Expected: 전부 PASS.

---

## Self-Review Notes

- **Spec coverage**: 스키마(`tr`/`lang`)=Task5/6, Argos 파이프라인=Task1–4, 멱등 백필=Task3/11, 하이브리드 UI(인라인 토글+팝오버)=Task8/9/10, `title_en`/`name_en` 폐지=Task5/6/9/10, 테스트=각 태스크, 롤아웃 순서=Phase A→B→Task11. 모두 매핑됨.
- **원문 언어 판정**: 스펙의 "country에서 도출" 대신 **스크립트 휴리스틱(필드별)**으로 단순화 — 작가 country 부재 문제를 피하고, 웹은 `tr[locale]` 존재 여부만으로 어포던스를 판단하므로 동작 동일. (스펙 대비 의도된 정제)
- **타입 일관성**: `TrMap`/`localized()`/`tr`/`lang` 명칭을 Phase B 전반에서 동일하게 사용. `field` 인자 문자열("title"/"name"/"region"/"description")은 Python `_FIELDS`와 일치.
- **확인 필요(실행 시)**: `cli.py`의 repo 오프너·로거·앱 엔트리포인트 실제 명칭(Task4 Step1), `LanguageProvider` STORAGE_KEY 값(Task7).
