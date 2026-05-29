# Crawler JSON Export Sink — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a `export-json` step that reads the canonical exhibition/venue/artist rows from the Repository and writes a single denormalized JSON snapshot (`web/public/data/exhibitions.json`) for the frontend to consume.

**Architecture:** A new pure builder (`build_catalog`) transforms the flat sheet-style rows (strings, comma-joined lists, `"TRUE"/"FALSE"`) into typed JSON, embedding each exhibition's venue and artists by id. A thin writer (`write_catalog`) serializes it to disk. A Typer CLI command (`export-json`) wires it to the live `GspreadRepository`. All logic is unit-tested against the in-memory `FakeRepository`.

**Tech Stack:** Python 3.12+, Pydantic models (existing), Typer CLI, pytest.

---

## Background for the implementer

- The canonical store is a Google Sheet with 4 relevant worksheets. The `Repository` protocol (`src/crawler/sinks/base.py`) exposes `read_rows(SheetName) -> list[dict]`. `SheetName` values: `EXHIBITIONS`, `ARTISTS`, `VENUES`, `ORGANIZERS`.
- Rows are **flat dicts of strings** (see `_exhibition_row`/`_venue_row`/`_artist_row` in `src/crawler/pipeline.py`). Conventions you must reverse:
  - Empty/optional → `""`.
  - Lists (`genre_tags`, `artist_ids`) → comma-joined string, e.g. `"a,b"`.
  - `featured` → `"TRUE"` / `"FALSE"`.
  - Numbers (`price_min`, `latitude`, …) → stored as int/float, but the live gspread backend may hand them back as strings. Parsers must accept both.
- Exhibition row keys you will read: `id, source, status, source_url, title, title_en, description, poster_image_url, medium, exhibition_type, genre_tags, fee_type, price_min, price_max, start_date, end_date, open_hours, artist_ids, venue_id, featured, popularity_score`.
- Venue row keys: `id, name, name_en, venue_type, region, district, address, country, latitude, longitude, website, open_hours_default`.
- Artist row keys: `id, name, name_en`.
- Test fakes live in `tests/conftest.py` (`FakeHeaderRepo`, `header_repo` fixture) and `src/crawler/sinks/fake.py` (`FakeRepository`). Use `FakeRepository` directly — seed rows with `append_rows`.
- Run all tests with `pytest -q`; lint with `ruff check src/ tests/`.

## File Structure

- **Create** `src/crawler/sinks/json_export.py` — parsers + `build_catalog(repo, generated_at)` + `write_catalog(repo, path, generated_at)`. Single responsibility: turn rows into the frontend JSON file.
- **Create** `tests/sinks/test_json_export.py` — unit tests for the builder, parsers, and writer.
- **Modify** `src/crawler/cli.py` — add the `export-json` command.

## JSON contract produced (target)

```json
{
  "generated_at": "2026-05-30T06:54:00+00:00",
  "exhibitions": [
    {
      "id": "e1", "title": "빛과 시간의 기록", "title_en": null,
      "poster_image_url": "https://example.com/p.jpg", "description": "…",
      "medium": "photo", "exhibition_type": "solo",
      "genre_tags": ["documentary"], "fee_type": "free",
      "price_min": null, "price_max": null,
      "start_date": "2026-05-30", "end_date": "2026-07-20",
      "status": "ongoing", "open_hours": "10:00–18:00",
      "venue": {"id": "v1", "name": "한미사진미술관", "region": "서울",
                "district": "삼청", "lat": 37.58, "lng": 126.98},
      "artists": [{"id": "a1", "name": "김작가"}],
      "source_url": "https://src/1", "featured": true, "popularity_score": null
    }
  ],
  "venues": [
    {"id": "v1", "name": "한미사진미술관", "name_en": "MoPS", "venue_type": "museum",
     "region": "서울", "district": "삼청", "address": "…", "country": "KR",
     "lat": 37.58, "lng": 126.98, "website": null}
  ],
  "artists": [{"id": "a1", "name": "김작가", "name_en": null}]
}
```

---

## Task 1: Field parsers

**Files:**
- Create: `src/crawler/sinks/json_export.py`
- Test: `tests/sinks/test_json_export.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/sinks/test_json_export.py
from crawler.sinks.json_export import (
    _bool,
    _float_or_none,
    _int_or_none,
    _split,
    _str_or_none,
)


def test_split_returns_list_or_empty():
    assert _split("a,b,c") == ["a", "b", "c"]
    assert _split("") == []
    assert _split("  a , b ") == ["a", "b"]


def test_str_or_none():
    assert _str_or_none("x") == "x"
    assert _str_or_none("") is None
    assert _str_or_none(None) is None


def test_int_or_none_accepts_str_and_int():
    assert _int_or_none(10000) == 10000
    assert _int_or_none("10000") == 10000
    assert _int_or_none("") is None
    assert _int_or_none(None) is None


def test_float_or_none_accepts_str_and_float():
    assert _float_or_none(37.58) == 37.58
    assert _float_or_none("126.98") == 126.98
    assert _float_or_none("") is None


def test_bool_reads_sheet_truthiness():
    assert _bool("TRUE") is True
    assert _bool(True) is True
    assert _bool("FALSE") is False
    assert _bool("") is False
    assert _bool(None) is False
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/sinks/test_json_export.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'crawler.sinks.json_export'`

- [ ] **Step 3: Write minimal implementation**

```python
# src/crawler/sinks/json_export.py
"""Export the canonical store to a denormalized JSON snapshot for the web frontend."""

from __future__ import annotations


def _split(value: object) -> list[str]:
    if not value:
        return []
    return [part.strip() for part in str(value).split(",") if part.strip()]


def _str_or_none(value: object) -> str | None:
    if value is None:
        return None
    text = str(value)
    return text if text != "" else None


def _int_or_none(value: object) -> int | None:
    if value is None or value == "":
        return None
    return int(value)


def _float_or_none(value: object) -> float | None:
    if value is None or value == "":
        return None
    return float(value)


def _bool(value: object) -> bool:
    if isinstance(value, bool):
        return value
    return str(value).strip().upper() == "TRUE"
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/sinks/test_json_export.py -v`
Expected: PASS (5 passed)

- [ ] **Step 5: Commit**

```bash
git add src/crawler/sinks/json_export.py tests/sinks/test_json_export.py
git commit -m "feat(sinks): json_export field parsers"
```

---

## Task 2: `build_catalog` — embed venue + artists

**Files:**
- Modify: `src/crawler/sinks/json_export.py`
- Test: `tests/sinks/test_json_export.py`

- [ ] **Step 1: Write the failing test**

```python
# append to tests/sinks/test_json_export.py
from datetime import UTC, datetime

from crawler.sinks.base import SheetName
from crawler.sinks.fake import FakeRepository
from crawler.sinks.json_export import build_catalog

GEN_AT = datetime(2026, 5, 30, 6, 54, tzinfo=UTC)


def _seed_repo() -> FakeRepository:
    repo = FakeRepository()
    repo.append_rows(SheetName.VENUES, [{
        "id": "v1", "name": "한미사진미술관", "name_en": "MoPS",
        "venue_type": "museum", "region": "서울", "district": "삼청",
        "address": "삼청로 9", "country": "KR",
        "latitude": 37.58, "longitude": 126.98, "website": "",
        "open_hours_default": "",
    }])
    repo.append_rows(SheetName.ARTISTS, [
        {"id": "a1", "name": "김작가", "name_en": ""},
        {"id": "a2", "name": "이작가", "name_en": "Lee"},
    ])
    repo.append_rows(SheetName.EXHIBITIONS, [{
        "id": "e1", "source": "artmap", "status": "ongoing",
        "source_url": "https://src/1", "title": "빛과 시간의 기록",
        "title_en": "", "description": "설명",
        "poster_image_url": "https://example.com/p.jpg",
        "medium": "photo", "exhibition_type": "solo",
        "genre_tags": "documentary,portrait", "fee_type": "free",
        "price_min": "", "price_max": "",
        "start_date": "2026-05-30", "end_date": "2026-07-20",
        "open_hours": "10:00–18:00", "artist_ids": "a1,a2", "venue_id": "v1",
        "featured": "TRUE", "popularity_score": "",
    }])
    return repo


def test_build_catalog_embeds_venue_and_artists():
    catalog = build_catalog(_seed_repo(), generated_at=GEN_AT)

    assert catalog["generated_at"] == "2026-05-30T06:54:00+00:00"
    assert len(catalog["exhibitions"]) == 1

    ex = catalog["exhibitions"][0]
    assert ex["id"] == "e1"
    assert ex["title"] == "빛과 시간의 기록"
    assert ex["title_en"] is None
    assert ex["genre_tags"] == ["documentary", "portrait"]
    assert ex["fee_type"] == "free"
    assert ex["price_min"] is None
    assert ex["featured"] is True
    assert ex["status"] == "ongoing"
    assert ex["venue"] == {
        "id": "v1", "name": "한미사진미술관", "region": "서울",
        "district": "삼청", "lat": 37.58, "lng": 126.98,
    }
    assert ex["artists"] == [
        {"id": "a1", "name": "김작가"},
        {"id": "a2", "name": "이작가"},
    ]


def test_build_catalog_lists_full_venues_and_artists():
    catalog = build_catalog(_seed_repo(), generated_at=GEN_AT)
    assert catalog["venues"][0]["lat"] == 37.58
    assert catalog["venues"][0]["website"] is None
    assert catalog["artists"][1] == {"id": "a2", "name": "이작가", "name_en": "Lee"}
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/sinks/test_json_export.py::test_build_catalog_embeds_venue_and_artists -v`
Expected: FAIL with `ImportError: cannot import name 'build_catalog'`

- [ ] **Step 3: Write minimal implementation**

```python
# append to src/crawler/sinks/json_export.py
from datetime import datetime

from crawler.sinks.base import Repository, SheetName


def _venue_full(row: dict) -> dict:
    return {
        "id": row["id"],
        "name": row.get("name", ""),
        "name_en": _str_or_none(row.get("name_en")),
        "venue_type": _str_or_none(row.get("venue_type")),
        "region": _str_or_none(row.get("region")),
        "district": _str_or_none(row.get("district")),
        "address": _str_or_none(row.get("address")),
        "country": _str_or_none(row.get("country")),
        "lat": _float_or_none(row.get("latitude")),
        "lng": _float_or_none(row.get("longitude")),
        "website": _str_or_none(row.get("website")),
    }


def _venue_embed(row: dict) -> dict:
    return {
        "id": row["id"],
        "name": row.get("name", ""),
        "region": _str_or_none(row.get("region")),
        "district": _str_or_none(row.get("district")),
        "lat": _float_or_none(row.get("latitude")),
        "lng": _float_or_none(row.get("longitude")),
    }


def _artist_full(row: dict) -> dict:
    return {
        "id": row["id"],
        "name": row.get("name", ""),
        "name_en": _str_or_none(row.get("name_en")),
    }


def _exhibition_json(row: dict, venues: dict[str, dict], artists: dict[str, dict]) -> dict:
    venue_id = _str_or_none(row.get("venue_id"))
    venue_row = venues.get(venue_id) if venue_id else None
    artist_ids = _split(row.get("artist_ids"))
    return {
        "id": row["id"],
        "title": row.get("title", ""),
        "title_en": _str_or_none(row.get("title_en")),
        "poster_image_url": _str_or_none(row.get("poster_image_url")),
        "description": _str_or_none(row.get("description")),
        "medium": _str_or_none(row.get("medium")),
        "exhibition_type": _str_or_none(row.get("exhibition_type")),
        "genre_tags": _split(row.get("genre_tags")),
        "fee_type": _str_or_none(row.get("fee_type")),
        "price_min": _int_or_none(row.get("price_min")),
        "price_max": _int_or_none(row.get("price_max")),
        "start_date": _str_or_none(row.get("start_date")),
        "end_date": _str_or_none(row.get("end_date")),
        "status": _str_or_none(row.get("status")),
        "open_hours": _str_or_none(row.get("open_hours")),
        "venue": _venue_embed(venue_row) if venue_row else None,
        "artists": [
            {"id": artists[aid]["id"], "name": artists[aid]["name"]}
            for aid in artist_ids
            if aid in artists
        ],
        "source_url": _str_or_none(row.get("source_url")),
        "featured": _bool(row.get("featured")),
        "popularity_score": _float_or_none(row.get("popularity_score")),
    }


def build_catalog(repo: Repository, generated_at: datetime) -> dict:
    venue_rows = repo.read_rows(SheetName.VENUES)
    artist_rows = repo.read_rows(SheetName.ARTISTS)
    exhibition_rows = repo.read_rows(SheetName.EXHIBITIONS)

    venues_by_id = {r["id"]: r for r in venue_rows}
    artists_by_id = {r["id"]: r for r in artist_rows}

    return {
        "generated_at": generated_at.isoformat(),
        "exhibitions": [
            _exhibition_json(r, venues_by_id, artists_by_id) for r in exhibition_rows
        ],
        "venues": [_venue_full(r) for r in venue_rows],
        "artists": [_artist_full(r) for r in artist_rows],
    }
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/sinks/test_json_export.py -v`
Expected: PASS (all tests in file)

- [ ] **Step 5: Commit**

```bash
git add src/crawler/sinks/json_export.py tests/sinks/test_json_export.py
git commit -m "feat(sinks): build_catalog joins venues + artists into frontend JSON"
```

---

## Task 3: Missing-reference & empty handling

**Files:**
- Test: `tests/sinks/test_json_export.py`

(No implementation change expected — this hardens the contract for sparse data. If a test fails, fix `build_catalog` to satisfy it.)

- [ ] **Step 1: Write the failing test**

```python
# append to tests/sinks/test_json_export.py
def test_build_catalog_handles_missing_venue_and_no_artists():
    repo = FakeRepository()
    repo.append_rows(SheetName.EXHIBITIONS, [{
        "id": "e9", "source": "artmap", "status": "upcoming",
        "source_url": "https://src/9", "title": "제목 없는 전시",
        "title_en": "", "description": "",
        "poster_image_url": "", "medium": "photo",
        "exhibition_type": "group", "genre_tags": "", "fee_type": "free",
        "price_min": "", "price_max": "",
        "start_date": "2026-06-20", "end_date": "", "open_hours": "",
        "artist_ids": "", "venue_id": "", "featured": "FALSE",
        "popularity_score": "",
    }])
    catalog = build_catalog(repo, generated_at=GEN_AT)
    ex = catalog["exhibitions"][0]
    assert ex["venue"] is None
    assert ex["artists"] == []
    assert ex["genre_tags"] == []
    assert ex["end_date"] is None
    assert ex["poster_image_url"] is None
    assert catalog["venues"] == []


def test_build_catalog_drops_unknown_artist_ids():
    repo = FakeRepository()
    repo.append_rows(SheetName.ARTISTS, [{"id": "a1", "name": "있는작가", "name_en": ""}])
    repo.append_rows(SheetName.EXHIBITIONS, [{
        "id": "e8", "source": "artmap", "status": "ongoing",
        "source_url": "https://src/8", "title": "T", "title_en": "",
        "description": "", "poster_image_url": "", "medium": "photo",
        "exhibition_type": "group", "genre_tags": "", "fee_type": "free",
        "price_min": "", "price_max": "", "start_date": "", "end_date": "",
        "open_hours": "", "artist_ids": "a1,ghost", "venue_id": "",
        "featured": "FALSE", "popularity_score": "",
    }])
    catalog = build_catalog(repo, generated_at=GEN_AT)
    assert catalog["exhibitions"][0]["artists"] == [{"id": "a1", "name": "있는작가"}]
```

- [ ] **Step 2: Run tests**

Run: `pytest tests/sinks/test_json_export.py -v`
Expected: PASS (these should pass against the Task 2 implementation; if not, fix `build_catalog`)

- [ ] **Step 3: Commit**

```bash
git add tests/sinks/test_json_export.py
git commit -m "test(sinks): json_export sparse-data + unknown-ref coverage"
```

---

## Task 4: `write_catalog` — serialize to disk

**Files:**
- Modify: `src/crawler/sinks/json_export.py`
- Test: `tests/sinks/test_json_export.py`

- [ ] **Step 1: Write the failing test**

```python
# append to tests/sinks/test_json_export.py
import json
from pathlib import Path

from crawler.sinks.json_export import write_catalog


def test_write_catalog_creates_parent_dirs_and_writes_json(tmp_path: Path):
    repo = _seed_repo()
    out = tmp_path / "nested" / "exhibitions.json"
    count = write_catalog(repo, str(out), generated_at=GEN_AT)

    assert count == 1
    assert out.exists()
    data = json.loads(out.read_text(encoding="utf-8"))
    assert data["generated_at"] == "2026-05-30T06:54:00+00:00"
    assert data["exhibitions"][0]["title"] == "빛과 시간의 기록"
    # Korean must not be escaped
    assert "\\u" not in out.read_text(encoding="utf-8")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/sinks/test_json_export.py::test_write_catalog_creates_parent_dirs_and_writes_json -v`
Expected: FAIL with `ImportError: cannot import name 'write_catalog'`

- [ ] **Step 3: Write minimal implementation**

```python
# append to src/crawler/sinks/json_export.py
import json
import os
from datetime import UTC


def write_catalog(
    repo: Repository, path: str, generated_at: datetime | None = None
) -> int:
    if generated_at is None:
        generated_at = datetime.now(UTC)
    catalog = build_catalog(repo, generated_at=generated_at)
    parent = os.path.dirname(path)
    if parent:
        os.makedirs(parent, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(catalog, f, ensure_ascii=False, indent=2)
    return len(catalog["exhibitions"])
```

Note: move the `import json`, `import os`, and `from datetime import UTC, datetime` lines to the top of the file with the other imports (don't leave them inline) so `ruff` stays clean. Final top-of-file imports should read:

```python
from __future__ import annotations

import json
import os
from datetime import UTC, datetime

from crawler.sinks.base import Repository, SheetName
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/sinks/test_json_export.py -v`
Expected: PASS (all)

- [ ] **Step 5: Commit**

```bash
git add src/crawler/sinks/json_export.py tests/sinks/test_json_export.py
git commit -m "feat(sinks): write_catalog serializes snapshot to disk"
```

---

## Task 5: CLI `export-json` command

**Files:**
- Modify: `src/crawler/cli.py`
- Test: `tests/test_cli.py`

- [ ] **Step 1: Write the failing test**

```python
# append to tests/test_cli.py
from typer.testing import CliRunner

from crawler.cli import app


def test_export_json_writes_file(tmp_path, monkeypatch):
    from crawler.sinks.base import SheetName
    from crawler.sinks.fake import FakeRepository

    repo = FakeRepository()
    repo.append_rows(SheetName.EXHIBITIONS, [{
        "id": "e1", "source": "artmap", "status": "ongoing",
        "source_url": "https://src/1", "title": "T", "title_en": "",
        "description": "", "poster_image_url": "", "medium": "photo",
        "exhibition_type": "solo", "genre_tags": "", "fee_type": "free",
        "price_min": "", "price_max": "", "start_date": "2026-05-30",
        "end_date": "2026-07-20", "open_hours": "", "artist_ids": "",
        "venue_id": "", "featured": "FALSE", "popularity_score": "",
    }])
    monkeypatch.setattr("crawler.cli._build_repo", lambda: repo)

    out = tmp_path / "exhibitions.json"
    result = CliRunner().invoke(app, ["export-json", "--out", str(out)])

    assert result.exit_code == 0, result.output
    assert out.exists()
    assert "1 exhibitions" in result.output
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_cli.py::test_export_json_writes_file -v`
Expected: FAIL — `export-json` is not a registered command (non-zero exit / usage error)

- [ ] **Step 3: Write minimal implementation**

```python
# add to src/crawler/cli.py, after the dry-run command (keep style consistent)
@app.command("export-json")
def export_json_cmd(
    out: str = "web/public/data/exhibitions.json",
) -> None:
    """Export the canonical store to a denormalized JSON snapshot for the web frontend."""
    from crawler.sinks.json_export import write_catalog

    count = write_catalog(_build_repo(), out)
    typer.echo(f"export-json: wrote {count} exhibitions to {out}")
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_cli.py::test_export_json_writes_file -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/crawler/cli.py tests/test_cli.py
git commit -m "feat(cli): export-json command"
```

---

## Task 6: Full suite + lint + docs

**Files:**
- Modify: `README.md`

- [ ] **Step 1: Run the whole suite**

Run: `pytest -q`
Expected: PASS (no regressions)

- [ ] **Step 2: Lint**

Run: `ruff check src/ tests/`
Expected: no errors. Fix any reported issues (most likely inline-import placement in `json_export.py`).

- [ ] **Step 3: Document the command in the CLI section of README.md**

Add this line to the `## CLI` fenced block in `README.md`, after the `run-all` line:

```
crawler export-json       # write web/public/data/exhibitions.json snapshot
```

- [ ] **Step 4: Commit**

```bash
git add README.md
git commit -m "docs: document export-json command"
```

---

## Self-Review (completed during planning)

**Spec coverage:** Implements spec §5.1 (static JSON snapshot) and §6 (catalog JSON shape, field derivation from `NormalizedExhibition`/`Venue`/`Artist`). Output path `web/public/data/exhibitions.json` matches §6. The GitHub Actions wiring to run `export-json` on a schedule and commit the result is intentionally deferred to the web-app plan (it depends on the `web/` directory existing).

**Placeholder scan:** No TBD/TODO. Every code step shows complete code; every command shows expected output.

**Type consistency:** `build_catalog(repo, generated_at)` and `write_catalog(repo, path, generated_at=None)` signatures are consistent across tasks. Helper names (`_split`, `_str_or_none`, `_int_or_none`, `_float_or_none`, `_bool`, `_venue_full`, `_venue_embed`, `_artist_full`, `_exhibition_json`) are used identically wherever referenced. The embedded-venue keys (`id,name,region,district,lat,lng`) match between `_venue_embed` and the Task 2 assertion.

**Note for executor:** `organizer_id`/organizers are deliberately excluded from the v1 catalog JSON — the frontend design (spec §4) does not surface organizers. Add later if a screen needs them.
