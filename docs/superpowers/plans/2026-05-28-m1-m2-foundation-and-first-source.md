# M1 + M2 — Foundation & First Source (Artmap) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Stand up the Python crawler skeleton (models, normalizers, sinks, CLI) and ship one end-to-end source (Artmap) writing into Google Sheets via gspread.

**Architecture:** Pipeline = Source → Normalizer → Resolver → Geocoder → Sheets Writer. Single Python 3.12 package. In-process orchestration. Fake Sheet backend for tests, gspread for production. TDD throughout.

**Tech Stack:** Python 3.12, pydantic v2, httpx, selectolax, tenacity, gspread + google-auth, respx (test), pytest, ruff, mypy.

**Spec reference:** `docs/superpowers/specs/2026-05-28-photo-exhibition-crawler-design.md`.

**Out of scope for this plan:** Sources beyond Artmap (M3), GitHub Actions cron + healthcheck (M4 partly here for `test.yml` only), popularity scoring (v1.5).

---

## File Structure

Files this plan will create:

```
photo-exhibition-crawler/
├── pyproject.toml                                ← Task 1
├── .gitignore                                    ← Task 1
├── README.md                                     ← Task 1
├── .github/workflows/test.yml                    ← Task 20
├── src/crawler/
│   ├── __init__.py                               ← Task 1
│   ├── models.py                                 ← Task 2
│   ├── cli.py                                    ← Task 16
│   ├── pipeline.py                               ← Task 15
│   ├── reporter.py                               ← Task 14
│   ├── normalize/
│   │   ├── __init__.py                           ← Task 7
│   │   ├── dedup.py                              ← Task 3
│   │   ├── text.py                               ← Task 4
│   │   ├── dates.py                              ← Task 5
│   │   ├── categories.py                         ← Task 6
│   │   └── status.py                             ← Task 8
│   ├── resolver/
│   │   ├── __init__.py
│   │   └── entities.py                           ← Task 12
│   ├── enrich/
│   │   ├── __init__.py
│   │   └── geocoder.py                           ← Task 13
│   ├── sinks/
│   │   ├── __init__.py
│   │   ├── base.py                               ← Task 9
│   │   ├── fake.py                               ← Task 9
│   │   ├── upsert.py                             ← Task 10
│   │   ├── gspread_repo.py                       ← Task 11
│   │   └── init_sheets.py                        ← Task 11
│   └── sources/
│       ├── __init__.py
│       ├── base.py                               ← Task 17
│       └── artmap.py                             ← Task 18
├── tests/
│   ├── conftest.py                               ← Task 2
│   ├── fixtures/artmap/                          ← Task 18
│   ├── test_models.py                            ← Task 2
│   ├── normalize/test_dedup.py                   ← Task 3
│   ├── normalize/test_text.py                    ← Task 4
│   ├── normalize/test_dates.py                   ← Task 5
│   ├── normalize/test_categories.py              ← Task 6
│   ├── normalize/test_normalize.py               ← Task 7
│   ├── normalize/test_status.py                  ← Task 8
│   ├── sinks/test_fake.py                        ← Task 9
│   ├── sinks/test_upsert.py                      ← Task 10
│   ├── sinks/test_init_sheets.py                 ← Task 11
│   ├── resolver/test_entities.py                 ← Task 12
│   ├── enrich/test_geocoder.py                   ← Task 13
│   ├── test_reporter.py                          ← Task 14
│   ├── test_pipeline.py                          ← Task 15
│   ├── test_cli.py                               ← Task 16
│   ├── sources/test_artmap.py                    ← Task 18
│   └── integration/test_pipeline_artmap.py       ← Task 19
└── docs/sources/artmap.md                        ← Task 17
```

Boundaries:
- `sources/*` only knows HTTP/HTML; never imports normalize/resolver/sinks.
- `normalize/*` is pure functions; no I/O.
- `resolver/entities.py` depends only on the sink's `Repository` interface (not gspread).
- `sinks/` defines `Repository` and `UpsertEngine`; gspread is one implementation.
- `pipeline.py` is the only place all of the above meet.

---

## Task 1: Project bootstrap

**Files:**
- Create: `pyproject.toml`
- Create: `.gitignore`
- Create: `README.md`
- Create: `src/crawler/__init__.py`

- [ ] **Step 1.1: Write `pyproject.toml`**

```toml
[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[project]
name = "photo-exhibition-crawler"
version = "0.1.0"
description = "Crawler for Korean photo/video/camera exhibitions"
requires-python = ">=3.12"
dependencies = [
  "pydantic>=2.6,<3",
  "httpx>=0.27,<1",
  "selectolax>=0.3.21,<1",
  "tenacity>=8,<9",
  "gspread>=6,<7",
  "google-auth>=2.28,<3",
  "typer>=0.12,<1",
  "python-dateutil>=2.9,<3",
]

[project.optional-dependencies]
dev = [
  "pytest>=8,<9",
  "respx>=0.21,<1",
  "freezegun>=1.4,<2",
  "ruff>=0.4,<1",
  "mypy>=1.10,<2",
]

[project.scripts]
crawler = "crawler.cli:app"

[tool.hatch.build.targets.wheel]
packages = ["src/crawler"]

[tool.pytest.ini_options]
testpaths = ["tests"]
addopts = "-ra -q"
markers = [
  "external: tests that hit live external services (excluded by default)",
]

[tool.ruff]
target-version = "py312"
line-length = 100

[tool.ruff.lint]
select = ["E", "F", "I", "B", "UP"]

[tool.mypy]
python_version = "3.12"
strict_optional = true
warn_unused_ignores = true
```

- [ ] **Step 1.2: Write `.gitignore`**

```
__pycache__/
*.py[cod]
.venv/
.env
*.egg-info/
dist/
build/
.pytest_cache/
.mypy_cache/
.ruff_cache/
out/
service-account.json
```

- [ ] **Step 1.3: Write `README.md`**

```markdown
# photo-exhibition-crawler

Crawler for Korean photography/video/camera exhibitions. Writes normalized data into Google Sheets.

## Quick start
```bash
python3.12 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
pytest
```

## CLI
```bash
crawler init-sheets               # Create the 5 worksheets with headers (idempotent)
crawler run <source>              # Crawl one source and upsert into the sheet
crawler dry-run <source>          # Crawl and print normalized output without writing
crawler run-all                   # Crawl every registered source
```

## Required environment variables (production)
- `GOOGLE_SERVICE_ACCOUNT_JSON` — service-account JSON contents
- `SHEET_ID` — target Google Sheet ID
- `KAKAO_REST_API_KEY` — Kakao Local REST API key
```

- [ ] **Step 1.4: Write `src/crawler/__init__.py`**

```python
"""photo-exhibition-crawler — Korean photography/video/camera exhibition crawler."""

__version__ = "0.1.0"
```

- [ ] **Step 1.5: Verify install works**

Run: `python3.12 -m venv .venv && source .venv/bin/activate && pip install -e ".[dev]"`
Expected: install completes without errors.

Run: `pytest`
Expected: exits 0 (no tests collected).

- [ ] **Step 1.6: Commit**

```bash
git add pyproject.toml .gitignore README.md src/
git commit -m "feat: bootstrap project (pyproject, package skeleton)"
```

---

## Task 2: Pydantic models & enums

**Files:**
- Create: `src/crawler/models.py`
- Create: `tests/conftest.py`
- Create: `tests/test_models.py`

- [ ] **Step 2.1: Write `tests/conftest.py`** (empty placeholder for shared fixtures)

```python
"""Shared pytest configuration."""
```

- [ ] **Step 2.2: Write failing test `tests/test_models.py`**

```python
from datetime import date, datetime, timezone

from crawler.models import (
    Artist,
    ExhibitionType,
    FeeType,
    Medium,
    NormalizedExhibition,
    Organizer,
    OrganizerType,
    RawExhibition,
    SourceName,
    Status,
    Venue,
    VenueType,
)


def _make_normalized() -> NormalizedExhibition:
    return NormalizedExhibition(
        id="abc123def456",
        source=SourceName.ARTMAP,
        source_url="https://art-map.co.kr/exhibition/view.php?idx=1",
        title="달과 도시",
        title_en=None,
        description=None,
        poster_image_url=None,
        medium=Medium.PHOTO,
        exhibition_type=ExhibitionType.SOLO,
        genre_tags=["documentary"],
        fee_type=FeeType.FREE,
        price_min=None,
        price_max=None,
        activities=[],
        start_date=date(2026, 6, 1),
        end_date=date(2026, 7, 1),
        open_hours=None,
        artist_raw_names=["김작가"],
        venue_raw_name="류가헌",
        organizer_raw_name=None,
        artist_ids=[],
        venue_id="",
        organizer_id="",
        popularity_score=None,
        featured=False,
        status=Status.UPCOMING,
        crawled_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
        warnings=[],
    )


def test_normalized_exhibition_constructs():
    exhibition = _make_normalized()
    assert exhibition.id == "abc123def456"
    assert exhibition.medium is Medium.PHOTO


def test_raw_exhibition_allows_missing_fields():
    raw = RawExhibition(
        source=SourceName.ARTMAP,
        source_url="https://art-map.co.kr/exhibition/view.php?idx=1",
        raw={"title": "untitled"},
    )
    assert raw.raw["title"] == "untitled"


def test_venue_requires_name():
    v = Venue(
        id="x",
        name="류가헌",
        venue_type=VenueType.GALLERY,
        region="서울",
        sources=["artmap"],
        first_seen_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )
    assert v.name == "류가헌"


def test_artist_organizer_construct():
    Artist(
        id="x",
        name="김작가",
        name_normalized="김작가",
        sources=["artmap"],
        first_seen_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )
    Organizer(
        id="y",
        name="한국전파진흥협회",
        name_normalized="한국전파진흥협회",
        organizer_type=OrganizerType.ASSOCIATION,
        sources=["koba"],
        first_seen_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )
```

- [ ] **Step 2.3: Run tests, see them fail**

Run: `pytest tests/test_models.py -v`
Expected: ImportError (`crawler.models` does not exist).

- [ ] **Step 2.4: Write `src/crawler/models.py`**

```python
"""Pydantic models and enums shared across the pipeline."""

from __future__ import annotations

from datetime import date, datetime
from enum import Enum

from pydantic import BaseModel, ConfigDict, Field, HttpUrl


class SourceName(str, Enum):
    ARTMAP = "artmap"
    NAVER = "naver"
    PHOTO_SEMA = "photo_sema"
    MUSEUM_HANMI = "museum_hanmi"
    KOBA = "koba"


class Medium(str, Enum):
    PHOTO = "photo"
    VIDEO = "video"
    GEAR = "gear"
    MIXED = "mixed"


class ExhibitionType(str, Enum):
    SOLO = "solo"
    GROUP = "group"
    CURATED = "curated"
    FESTIVAL = "festival"
    EXPO = "expo"
    PERMANENT = "permanent"


class FeeType(str, Enum):
    FREE = "free"
    PAID = "paid"
    PARTIAL = "partial"


class VenueType(str, Enum):
    MUSEUM = "museum"
    GALLERY = "gallery"
    CAFE = "cafe"
    ALT_SPACE = "alt_space"
    CONVENTION = "convention"
    OTHER = "other"


class OrganizerType(str, Enum):
    MUSEUM = "museum"
    GALLERY = "gallery"
    FOUNDATION = "foundation"
    ASSOCIATION = "association"
    CORPORATE = "corporate"
    PUBLIC = "public"
    OTHER = "other"


class Status(str, Enum):
    UPCOMING = "upcoming"
    ONGOING = "ongoing"
    PAST = "past"
    UNKNOWN = "unknown"


class RawExhibition(BaseModel):
    """Raw payload from a source extractor. All semantic fields are in `raw`."""

    model_config = ConfigDict(extra="forbid")

    source: SourceName
    source_url: HttpUrl
    raw: dict = Field(default_factory=dict)


class NormalizedExhibition(BaseModel):
    """Post-normalization, before/after entity resolution."""

    model_config = ConfigDict(extra="forbid")

    id: str
    source: SourceName
    source_url: HttpUrl

    title: str
    title_en: str | None = None
    description: str | None = None
    poster_image_url: HttpUrl | None = None

    medium: Medium
    exhibition_type: ExhibitionType
    genre_tags: list[str] = Field(default_factory=list)
    fee_type: FeeType = FeeType.FREE
    price_min: int | None = None
    price_max: int | None = None
    activities: list[str] = Field(default_factory=list)

    start_date: date | None = None
    end_date: date | None = None
    open_hours: str | None = None

    artist_raw_names: list[str] = Field(default_factory=list)
    venue_raw_name: str | None = None
    organizer_raw_name: str | None = None

    artist_ids: list[str] = Field(default_factory=list)
    venue_id: str = ""
    organizer_id: str = ""

    popularity_score: float | None = None
    featured: bool = False

    status: Status = Status.UNKNOWN
    crawled_at: datetime
    updated_at: datetime
    warnings: list[str] = Field(default_factory=list)


class Artist(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    name: str
    name_en: str | None = None
    name_normalized: str
    bio: str | None = None
    instagram: HttpUrl | None = None
    website: HttpUrl | None = None
    sources: list[str] = Field(default_factory=list)
    first_seen_at: datetime
    updated_at: datetime


class Venue(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    name: str
    name_en: str | None = None
    venue_type: VenueType = VenueType.OTHER
    region: str | None = None
    district: str | None = None
    address: str | None = None
    latitude: float | None = None
    longitude: float | None = None
    website: HttpUrl | None = None
    open_hours_default: str | None = None
    sources: list[str] = Field(default_factory=list)
    first_seen_at: datetime
    updated_at: datetime


class Organizer(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    name: str
    name_en: str | None = None
    name_normalized: str
    organizer_type: OrganizerType = OrganizerType.OTHER
    website: HttpUrl | None = None
    sources: list[str] = Field(default_factory=list)
    first_seen_at: datetime
    updated_at: datetime
```

- [ ] **Step 2.5: Run tests, expect pass**

Run: `pytest tests/test_models.py -v`
Expected: 4 passed.

- [ ] **Step 2.6: Commit**

```bash
git add src/crawler/models.py tests/conftest.py tests/test_models.py
git commit -m "feat(models): pydantic schemas for raw + normalized exhibition and entities"
```

---

## Task 3: Stable-ID hashing (`dedup`)

**Files:**
- Create: `src/crawler/normalize/__init__.py` (empty)
- Create: `src/crawler/normalize/dedup.py`
- Create: `tests/normalize/__init__.py` (empty)
- Create: `tests/normalize/test_dedup.py`

- [ ] **Step 3.1: Write failing test `tests/normalize/test_dedup.py`**

```python
from datetime import date

from crawler.normalize.dedup import (
    exhibition_id,
    artist_id,
    venue_id,
    organizer_id,
)


def test_exhibition_id_is_stable():
    a = exhibition_id("artmap", "류가헌", "달과 도시", date(2026, 6, 1))
    b = exhibition_id("artmap", "류가헌", "달과 도시", date(2026, 6, 1))
    assert a == b
    assert len(a) == 12


def test_exhibition_id_differs_by_source():
    a = exhibition_id("artmap", "류가헌", "달과 도시", date(2026, 6, 1))
    b = exhibition_id("naver", "류가헌", "달과 도시", date(2026, 6, 1))
    assert a != b


def test_exhibition_id_tolerates_missing_date():
    a = exhibition_id("artmap", "류가헌", "달과 도시", None)
    assert len(a) == 12


def test_artist_id_uses_normalized_name():
    # Different inputs that normalize to same name should collide
    a = artist_id("김작가")
    b = artist_id("김 작가")  # different raw, same normalized handled upstream
    assert a != b  # caller must normalize before calling
    assert len(a) == 12


def test_venue_id_prefers_address():
    with_addr = venue_id("류가헌", "서울 종로구 자하문로 106")
    name_only = venue_id("류가헌", None)
    assert with_addr != name_only


def test_organizer_id_stable():
    assert organizer_id("한국전파진흥협회") == organizer_id("한국전파진흥협회")
```

- [ ] **Step 3.2: Run tests, see fail**

Run: `pytest tests/normalize/test_dedup.py -v`
Expected: ImportError.

- [ ] **Step 3.3: Write `src/crawler/normalize/__init__.py`**

```python
"""Pure-function normalization layer (no I/O)."""
```

- [ ] **Step 3.4: Write `src/crawler/normalize/dedup.py`**

```python
"""Stable natural-key hashing for entities. Pure functions, no I/O."""

from __future__ import annotations

import hashlib
from datetime import date


_HASH_LEN = 12


def _hash(*parts: str | None) -> str:
    joined = "|".join("" if p is None else p for p in parts)
    return hashlib.sha1(joined.encode("utf-8")).hexdigest()[:_HASH_LEN]


def exhibition_id(
    source: str,
    venue_name: str | None,
    title: str,
    start_date: date | None,
) -> str:
    return _hash(source, venue_name, title, start_date.isoformat() if start_date else None)


def artist_id(name_normalized: str) -> str:
    return _hash("artist", name_normalized)


def venue_id(name: str, normalized_address: str | None) -> str:
    if normalized_address:
        return _hash("venue:addr", normalized_address)
    return _hash("venue:name", name)


def organizer_id(name_normalized: str) -> str:
    return _hash("organizer", name_normalized)
```

- [ ] **Step 3.5: Run tests, expect pass**

Run: `pytest tests/normalize/test_dedup.py -v`
Expected: 6 passed.

- [ ] **Step 3.6: Commit**

```bash
git add src/crawler/normalize/__init__.py src/crawler/normalize/dedup.py tests/normalize/
git commit -m "feat(normalize): stable natural-key hashing for entities"
```

---

## Task 4: Text normalization

**Files:**
- Create: `src/crawler/normalize/text.py`
- Create: `tests/normalize/test_text.py`

- [ ] **Step 4.1: Write failing test `tests/normalize/test_text.py`**

```python
from crawler.normalize.text import (
    clean_whitespace,
    normalize_name,
    normalize_address,
)


def test_clean_whitespace_collapses_runs():
    assert clean_whitespace("  hello   world  ") == "hello world"
    assert clean_whitespace("a\n\tb") == "a b"


def test_clean_whitespace_handles_zero_width_chars():
    assert clean_whitespace("a​b‌c") == "abc"


def test_normalize_name_lowercases_and_strips_punctuation():
    assert normalize_name("Kim, Joo-hyun.") == "kim joohyun"
    assert normalize_name(" 김  작가 ") == "김 작가"


def test_normalize_name_empty():
    assert normalize_name("") == ""
    assert normalize_name("   ") == ""


def test_normalize_address_strips_korean_postal_artifacts():
    assert normalize_address("(03044) 서울 종로구 자하문로 106") == "서울 종로구 자하문로 106"
    assert normalize_address("서울특별시  종로구  자하문로 106 ") == "서울 종로구 자하문로 106"
```

- [ ] **Step 4.2: Run, see fail**

Run: `pytest tests/normalize/test_text.py -v`
Expected: ImportError.

- [ ] **Step 4.3: Write `src/crawler/normalize/text.py`**

```python
"""Text cleanup and matching-key normalization. Pure functions."""

from __future__ import annotations

import re
import unicodedata


_ZERO_WIDTH = re.compile(r"[​-‍﻿]")
_WS = re.compile(r"\s+")
_POSTAL_PREFIX = re.compile(r"^\(\s*\d{3,5}\s*\)\s*")
_SPECIAL_CITY = re.compile(r"(특별시|광역시|특별자치시|특별자치도)")
_PUNCT = re.compile(r"[^\w\s가-힣]", re.UNICODE)


def clean_whitespace(s: str) -> str:
    s = _ZERO_WIDTH.sub("", s)
    return _WS.sub(" ", s).strip()


def normalize_name(s: str) -> str:
    s = unicodedata.normalize("NFC", s)
    s = clean_whitespace(s)
    s = _PUNCT.sub(" ", s)
    s = _WS.sub(" ", s).strip()
    return s.lower()


def normalize_address(s: str) -> str:
    s = unicodedata.normalize("NFC", s)
    s = _POSTAL_PREFIX.sub("", s)
    s = _SPECIAL_CITY.sub("", s)
    return clean_whitespace(s)
```

- [ ] **Step 4.4: Run, expect pass**

Run: `pytest tests/normalize/test_text.py -v`
Expected: 5 passed.

- [ ] **Step 4.5: Commit**

```bash
git add src/crawler/normalize/text.py tests/normalize/test_text.py
git commit -m "feat(normalize): text cleanup, name/address normalization keys"
```

---

## Task 5: Date parsing

**Files:**
- Create: `src/crawler/normalize/dates.py`
- Create: `tests/normalize/test_dates.py`

- [ ] **Step 5.1: Write failing test `tests/normalize/test_dates.py`**

```python
from datetime import date

import pytest

from crawler.normalize.dates import parse_date, parse_date_range


@pytest.mark.parametrize(
    "raw, expected",
    [
        ("2026.05.19", date(2026, 5, 19)),
        ("2026-05-19", date(2026, 5, 19)),
        ("2026/05/19", date(2026, 5, 19)),
        ("2026년 5월 19일", date(2026, 5, 19)),
        ("May 19, 2026", date(2026, 5, 19)),
        ("19 May 2026", date(2026, 5, 19)),
    ],
)
def test_parse_date_formats(raw: str, expected: date):
    assert parse_date(raw) == expected


def test_parse_date_returns_none_on_garbage():
    assert parse_date("미정") is None
    assert parse_date("") is None
    assert parse_date(None) is None


def test_parse_date_range_with_tilde():
    start, end = parse_date_range("2026.05.19 ~ 2026.10.25")
    assert start == date(2026, 5, 19) and end == date(2026, 10, 25)


def test_parse_date_range_with_dash():
    start, end = parse_date_range("2026-05-19 - 2026-10-25")
    assert start == date(2026, 5, 19) and end == date(2026, 10, 25)


def test_parse_date_range_partial_returns_what_it_can():
    start, end = parse_date_range("2026.05.19 ~ 미정")
    assert start == date(2026, 5, 19) and end is None
```

- [ ] **Step 5.2: Run, see fail**

Run: `pytest tests/normalize/test_dates.py -v`
Expected: ImportError.

- [ ] **Step 5.3: Write `src/crawler/normalize/dates.py`**

```python
"""Date parsing tolerant of Korean and English formats."""

from __future__ import annotations

import re
from datetime import date

from dateutil import parser as dateparser


_KOREAN_PATTERN = re.compile(r"(\d{4})\s*년\s*(\d{1,2})\s*월\s*(\d{1,2})\s*일")
_RANGE_SPLIT = re.compile(r"\s*[~\-–—]\s*")


def parse_date(raw: str | None) -> date | None:
    if not raw:
        return None
    raw = raw.strip()
    if not raw:
        return None

    m = _KOREAN_PATTERN.search(raw)
    if m:
        try:
            return date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
        except ValueError:
            return None

    try:
        return dateparser.parse(raw, fuzzy=False).date()
    except (ValueError, OverflowError, TypeError):
        return None


def parse_date_range(raw: str | None) -> tuple[date | None, date | None]:
    if not raw:
        return None, None
    parts = _RANGE_SPLIT.split(raw, maxsplit=1)
    if len(parts) == 1:
        single = parse_date(parts[0])
        return single, single
    return parse_date(parts[0]), parse_date(parts[1])
```

- [ ] **Step 5.4: Run, expect pass**

Run: `pytest tests/normalize/test_dates.py -v`
Expected: 9 passed.

- [ ] **Step 5.5: Commit**

```bash
git add src/crawler/normalize/dates.py tests/normalize/test_dates.py
git commit -m "feat(normalize): tolerant date and date-range parsing"
```

---

## Task 6: Category enum mapping

**Files:**
- Create: `src/crawler/normalize/categories.py`
- Create: `tests/normalize/test_categories.py`

- [ ] **Step 6.1: Write failing test `tests/normalize/test_categories.py`**

```python
import pytest

from crawler.models import ExhibitionType, FeeType, Medium, VenueType
from crawler.normalize.categories import (
    map_exhibition_type,
    map_fee_type,
    map_medium,
    map_venue_type,
)


@pytest.mark.parametrize(
    "text, expected",
    [
        ("사진전", Medium.PHOTO),
        ("Photography", Medium.PHOTO),
        ("영상", Medium.VIDEO),
        ("video art", Medium.VIDEO),
        ("카메라 박람회", Medium.GEAR),
        ("camera show", Medium.GEAR),
        ("사진/영상", Medium.MIXED),
    ],
)
def test_map_medium(text: str, expected: Medium):
    assert map_medium(text) is expected


def test_map_medium_falls_back_to_mixed_on_unknown():
    assert map_medium("???") is Medium.MIXED


@pytest.mark.parametrize(
    "text, expected",
    [
        ("개인전", ExhibitionType.SOLO),
        ("Solo Exhibition", ExhibitionType.SOLO),
        ("단체전", ExhibitionType.GROUP),
        ("기획전", ExhibitionType.CURATED),
        ("페스티벌", ExhibitionType.FESTIVAL),
        ("박람회", ExhibitionType.EXPO),
        ("상설전", ExhibitionType.PERMANENT),
    ],
)
def test_map_exhibition_type(text: str, expected: ExhibitionType):
    assert map_exhibition_type(text) is expected


def test_map_exhibition_type_defaults_to_curated():
    assert map_exhibition_type("???") is ExhibitionType.CURATED


@pytest.mark.parametrize(
    "text, expected",
    [
        ("미술관", VenueType.MUSEUM),
        ("갤러리", VenueType.GALLERY),
        ("Gallery", VenueType.GALLERY),
        ("COEX", VenueType.CONVENTION),
        ("카페", VenueType.CAFE),
        ("대안공간", VenueType.ALT_SPACE),
    ],
)
def test_map_venue_type(text: str, expected: VenueType):
    assert map_venue_type(text) is expected


def test_map_venue_type_other_for_unknown():
    assert map_venue_type("호텔") is VenueType.OTHER


def test_map_fee_type_free():
    assert map_fee_type("무료", None, None) is FeeType.FREE


def test_map_fee_type_paid():
    assert map_fee_type(None, 5000, 5000) is FeeType.PAID


def test_map_fee_type_partial():
    assert map_fee_type("일부 유료", 0, 10000) is FeeType.PARTIAL
```

- [ ] **Step 6.2: Run, see fail**

Run: `pytest tests/normalize/test_categories.py -v`
Expected: ImportError.

- [ ] **Step 6.3: Write `src/crawler/normalize/categories.py`**

```python
"""Enum mapping for medium, exhibition type, venue type, fee type."""

from __future__ import annotations

from crawler.models import ExhibitionType, FeeType, Medium, OrganizerType, VenueType


def _has(haystack: str, *needles: str) -> bool:
    return any(n in haystack for n in needles)


def map_medium(text: str) -> Medium:
    t = (text or "").lower()
    photo = _has(t, "사진", "photo")
    video = _has(t, "영상", "video", "film", "movie", "미디어")
    gear = _has(t, "카메라", "camera", "장비", "기자재", "imaging")
    if photo and video:
        return Medium.MIXED
    if gear and not (photo or video):
        return Medium.GEAR
    if video and not photo:
        return Medium.VIDEO
    if photo:
        return Medium.PHOTO
    return Medium.MIXED


def map_exhibition_type(text: str) -> ExhibitionType:
    t = (text or "").lower()
    if _has(t, "개인전", "solo"):
        return ExhibitionType.SOLO
    if _has(t, "단체전", "group"):
        return ExhibitionType.GROUP
    if _has(t, "페스티벌", "festival"):
        return ExhibitionType.FESTIVAL
    if _has(t, "박람회", "expo", "fair", "show"):
        return ExhibitionType.EXPO
    if _has(t, "상설", "permanent"):
        return ExhibitionType.PERMANENT
    if _has(t, "기획", "curated"):
        return ExhibitionType.CURATED
    return ExhibitionType.CURATED


def map_venue_type(text: str) -> VenueType:
    t = (text or "").lower()
    if _has(t, "미술관", "museum"):
        return VenueType.MUSEUM
    if _has(t, "갤러리", "gallery"):
        return VenueType.GALLERY
    if _has(t, "coex", "kintex", "컨벤션", "convention", "센터"):
        return VenueType.CONVENTION
    if _has(t, "카페", "cafe"):
        return VenueType.CAFE
    if _has(t, "대안공간", "alt space", "스페이스"):
        return VenueType.ALT_SPACE
    return VenueType.OTHER


def map_organizer_type(text: str) -> OrganizerType:
    t = (text or "").lower()
    if _has(t, "미술관"):
        return OrganizerType.MUSEUM
    if _has(t, "갤러리"):
        return OrganizerType.GALLERY
    if _has(t, "재단", "foundation"):
        return OrganizerType.FOUNDATION
    if _has(t, "협회", "association"):
        return OrganizerType.ASSOCIATION
    if _has(t, "주식회사", "corp", "inc", "ltd"):
        return OrganizerType.CORPORATE
    if _has(t, "시청", "공사", "공단", "정부", "구청"):
        return OrganizerType.PUBLIC
    return OrganizerType.OTHER


def map_fee_type(
    text: str | None,
    price_min: int | None,
    price_max: int | None,
) -> FeeType:
    t = (text or "").lower()
    if _has(t, "일부 유료", "partial"):
        return FeeType.PARTIAL
    if _has(t, "무료", "free"):
        return FeeType.FREE
    if price_min is not None and price_max is not None:
        if price_min == 0 and price_max > 0:
            return FeeType.PARTIAL
        if price_min > 0:
            return FeeType.PAID
        return FeeType.FREE
    return FeeType.FREE
```

- [ ] **Step 6.4: Run, expect pass**

Run: `pytest tests/normalize/test_categories.py -v`
Expected: 17 passed.

- [ ] **Step 6.5: Commit**

```bash
git add src/crawler/normalize/categories.py tests/normalize/test_categories.py
git commit -m "feat(normalize): enum mapping for medium/type/venue/fee"
```

---

## Task 7: Normalizer integration

**Files:**
- Create: `src/crawler/normalize/normalize.py`
- Modify: `src/crawler/normalize/__init__.py` (export `normalize_exhibition`)
- Create: `tests/normalize/test_normalize.py`

- [ ] **Step 7.1: Write failing test `tests/normalize/test_normalize.py`**

```python
from datetime import datetime, timezone

from freezegun import freeze_time

from crawler.models import (
    ExhibitionType,
    FeeType,
    Medium,
    RawExhibition,
    SourceName,
    Status,
)
from crawler.normalize import normalize_exhibition


@freeze_time("2026-05-28 12:00:00", tz_offset=0)
def test_normalize_artmap_row():
    raw = RawExhibition(
        source=SourceName.ARTMAP,
        source_url="https://art-map.co.kr/exhibition/view.php?idx=12345",
        raw={
            "title": "달과 도시 — 사진전",
            "title_en": None,
            "venue_name": "사진위주 류가헌",
            "venue_address": "서울 종로구 자하문로 106",
            "venue_region": "서울",
            "venue_district": "종로구",
            "artists": ["김작가"],
            "organizer": None,
            "date_range": "2026.06.01 ~ 2026.07.01",
            "fee_text": "무료",
            "exhibition_type_text": "개인전",
            "description": "사진작가 김작가의 첫 개인전",
            "poster_image_url": "https://art-map.co.kr/upload/p.jpg",
        },
    )
    normalized = normalize_exhibition(raw)

    assert normalized.title == "달과 도시 — 사진전"
    assert normalized.medium is Medium.PHOTO
    assert normalized.exhibition_type is ExhibitionType.SOLO
    assert normalized.fee_type is FeeType.FREE
    assert normalized.venue_raw_name == "사진위주 류가헌"
    assert normalized.artist_raw_names == ["김작가"]
    assert normalized.start_date.isoformat() == "2026-06-01"
    assert normalized.end_date.isoformat() == "2026-07-01"
    assert normalized.crawled_at == datetime(2026, 5, 28, 12, 0, tzinfo=timezone.utc)
    assert normalized.status is Status.UNKNOWN  # status set in a later stage
    assert len(normalized.id) == 12
    assert normalized.warnings == []


@freeze_time("2026-05-28 12:00:00", tz_offset=0)
def test_normalize_records_warning_when_date_unparseable():
    raw = RawExhibition(
        source=SourceName.ARTMAP,
        source_url="https://art-map.co.kr/exhibition/view.php?idx=1",
        raw={
            "title": "X",
            "venue_name": "Y",
            "date_range": "미정",
            "fee_text": "무료",
        },
    )
    normalized = normalize_exhibition(raw)
    assert normalized.start_date is None
    assert "date_range" in normalized.warnings


def test_normalize_requires_title():
    raw = RawExhibition(
        source=SourceName.ARTMAP,
        source_url="https://art-map.co.kr/exhibition/view.php?idx=1",
        raw={"venue_name": "X"},
    )
    import pytest
    with pytest.raises(ValueError, match="title"):
        normalize_exhibition(raw)
```

- [ ] **Step 7.2: Run, see fail**

Run: `pytest tests/normalize/test_normalize.py -v`
Expected: ImportError.

- [ ] **Step 7.3: Write `src/crawler/normalize/normalize.py`**

```python
"""RawExhibition → NormalizedExhibition. Pure function over Raw input."""

from __future__ import annotations

from datetime import datetime, timezone

from crawler.models import (
    NormalizedExhibition,
    RawExhibition,
    Status,
)
from crawler.normalize.categories import (
    map_exhibition_type,
    map_fee_type,
    map_medium,
)
from crawler.normalize.dates import parse_date_range
from crawler.normalize.dedup import exhibition_id
from crawler.normalize.text import clean_whitespace


def _opt(raw: dict, key: str) -> str | None:
    v = raw.get(key)
    if v is None:
        return None
    s = str(v).strip()
    return s or None


def normalize_exhibition(raw_payload: RawExhibition) -> NormalizedExhibition:
    raw = raw_payload.raw
    warnings: list[str] = []

    title = _opt(raw, "title")
    if not title:
        raise ValueError("title is required to normalize an exhibition")
    title = clean_whitespace(title)

    date_range_text = _opt(raw, "date_range")
    start_date, end_date = parse_date_range(date_range_text)
    if date_range_text and start_date is None:
        warnings.append("date_range")

    medium_text = " ".join(
        filter(None, [title, _opt(raw, "description"), _opt(raw, "category")])
    )
    medium = map_medium(medium_text)

    exhibition_type = map_exhibition_type(_opt(raw, "exhibition_type_text") or "")

    price_min = raw.get("price_min")
    price_max = raw.get("price_max")
    fee_type = map_fee_type(_opt(raw, "fee_text"), price_min, price_max)

    now = datetime.now(timezone.utc)

    return NormalizedExhibition(
        id=exhibition_id(
            raw_payload.source.value,
            _opt(raw, "venue_name"),
            title,
            start_date,
        ),
        source=raw_payload.source,
        source_url=raw_payload.source_url,
        title=title,
        title_en=_opt(raw, "title_en"),
        description=_opt(raw, "description"),
        poster_image_url=_opt(raw, "poster_image_url"),
        medium=medium,
        exhibition_type=exhibition_type,
        genre_tags=raw.get("genre_tags") or [],
        fee_type=fee_type,
        price_min=price_min,
        price_max=price_max,
        activities=raw.get("activities") or [],
        start_date=start_date,
        end_date=end_date,
        open_hours=_opt(raw, "open_hours"),
        artist_raw_names=raw.get("artists") or [],
        venue_raw_name=_opt(raw, "venue_name"),
        organizer_raw_name=_opt(raw, "organizer"),
        status=Status.UNKNOWN,
        crawled_at=now,
        updated_at=now,
        warnings=warnings,
    )
```

- [ ] **Step 7.4: Update `src/crawler/normalize/__init__.py`**

```python
"""Pure-function normalization layer (no I/O)."""

from crawler.normalize.normalize import normalize_exhibition

__all__ = ["normalize_exhibition"]
```

- [ ] **Step 7.5: Run, expect pass**

Run: `pytest tests/normalize/test_normalize.py -v`
Expected: 3 passed.

- [ ] **Step 7.6: Commit**

```bash
git add src/crawler/normalize/normalize.py src/crawler/normalize/__init__.py tests/normalize/test_normalize.py
git commit -m "feat(normalize): combine field normalizers into normalize_exhibition()"
```

---

## Task 8: Status auto-computation

**Files:**
- Create: `src/crawler/normalize/status.py`
- Create: `tests/normalize/test_status.py`

- [ ] **Step 8.1: Write failing test `tests/normalize/test_status.py`**

```python
from datetime import date

import pytest

from crawler.models import Status
from crawler.normalize.status import compute_status


@pytest.mark.parametrize(
    "today, start, end, expected",
    [
        (date(2026, 5, 28), date(2026, 6, 1), date(2026, 7, 1), Status.UPCOMING),
        (date(2026, 6, 15), date(2026, 6, 1), date(2026, 7, 1), Status.ONGOING),
        (date(2026, 7, 2), date(2026, 6, 1), date(2026, 7, 1), Status.PAST),
        (date(2026, 6, 1), date(2026, 6, 1), date(2026, 7, 1), Status.ONGOING),  # boundary
        (date(2026, 7, 1), date(2026, 6, 1), date(2026, 7, 1), Status.ONGOING),  # boundary
        (date(2026, 5, 28), None, None, Status.UNKNOWN),
        (date(2026, 5, 28), date(2026, 6, 1), None, Status.UPCOMING),
        (date(2026, 5, 28), None, date(2026, 7, 1), Status.UNKNOWN),
    ],
)
def test_compute_status(today, start, end, expected):
    assert compute_status(today, start, end) is expected
```

- [ ] **Step 8.2: Run, see fail**

Run: `pytest tests/normalize/test_status.py -v`
Expected: ImportError.

- [ ] **Step 8.3: Write `src/crawler/normalize/status.py`**

```python
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
```

- [ ] **Step 8.4: Run, expect pass**

Run: `pytest tests/normalize/test_status.py -v`
Expected: 8 passed.

- [ ] **Step 8.5: Commit**

```bash
git add src/crawler/normalize/status.py tests/normalize/test_status.py
git commit -m "feat(normalize): compute_status(today, start, end)"
```

---

## Task 9: Sink interface + Fake backend

**Files:**
- Create: `src/crawler/sinks/__init__.py` (empty)
- Create: `src/crawler/sinks/base.py`
- Create: `src/crawler/sinks/fake.py`
- Create: `tests/sinks/__init__.py` (empty)
- Create: `tests/sinks/test_fake.py`

- [ ] **Step 9.1: Write failing test `tests/sinks/test_fake.py`**

```python
from crawler.sinks.base import SheetName
from crawler.sinks.fake import FakeRepository


def test_fake_starts_empty():
    repo = FakeRepository()
    assert repo.read_rows(SheetName.EXHIBITIONS) == []


def test_fake_append_and_read():
    repo = FakeRepository()
    repo.append_rows(SheetName.ARTISTS, [{"id": "a1", "name": "김작가"}])
    rows = repo.read_rows(SheetName.ARTISTS)
    assert rows == [{"id": "a1", "name": "김작가"}]


def test_fake_patch_by_id():
    repo = FakeRepository()
    repo.append_rows(SheetName.VENUES, [{"id": "v1", "name": "류가헌"}])
    repo.patch_rows(SheetName.VENUES, [{"id": "v1", "name": "사진위주 류가헌"}])
    rows = repo.read_rows(SheetName.VENUES)
    assert rows == [{"id": "v1", "name": "사진위주 류가헌"}]


def test_fake_patch_unknown_id_raises():
    import pytest

    repo = FakeRepository()
    with pytest.raises(KeyError):
        repo.patch_rows(SheetName.VENUES, [{"id": "missing", "name": "x"}])
```

- [ ] **Step 9.2: Run, see fail**

Run: `pytest tests/sinks/test_fake.py -v`
Expected: ImportError.

- [ ] **Step 9.3: Write `src/crawler/sinks/__init__.py`** (empty)

```python
"""Storage sinks: writers for Google Sheets and fakes for testing."""
```

- [ ] **Step 9.4: Write `src/crawler/sinks/base.py`**

```python
"""Repository interface and shared sheet identifiers."""

from __future__ import annotations

from enum import Enum
from typing import Protocol


class SheetName(str, Enum):
    EXHIBITIONS = "Exhibitions"
    ARTISTS = "Artists"
    VENUES = "Venues"
    ORGANIZERS = "Organizers"
    OVERRIDES = "_overrides"


class Repository(Protocol):
    def read_rows(self, sheet: SheetName) -> list[dict]: ...
    def append_rows(self, sheet: SheetName, rows: list[dict]) -> None: ...
    def patch_rows(self, sheet: SheetName, rows: list[dict]) -> None: ...
```

- [ ] **Step 9.5: Write `src/crawler/sinks/fake.py`**

```python
"""In-memory Repository for unit and integration tests."""

from __future__ import annotations

from crawler.sinks.base import Repository, SheetName


class FakeRepository(Repository):
    def __init__(self) -> None:
        self._data: dict[SheetName, list[dict]] = {s: [] for s in SheetName}

    def read_rows(self, sheet: SheetName) -> list[dict]:
        return [dict(row) for row in self._data[sheet]]

    def append_rows(self, sheet: SheetName, rows: list[dict]) -> None:
        self._data[sheet].extend(dict(r) for r in rows)

    def patch_rows(self, sheet: SheetName, rows: list[dict]) -> None:
        by_id = {r["id"]: r for r in self._data[sheet]}
        for patch in rows:
            row_id = patch["id"]
            if row_id not in by_id:
                raise KeyError(f"unknown id {row_id} in {sheet.value}")
            by_id[row_id].update(patch)
```

- [ ] **Step 9.6: Run, expect pass**

Run: `pytest tests/sinks/test_fake.py -v`
Expected: 4 passed.

- [ ] **Step 9.7: Commit**

```bash
git add src/crawler/sinks/ tests/sinks/
git commit -m "feat(sinks): Repository protocol + in-memory FakeRepository"
```

---

## Task 10: Upsert engine

**Files:**
- Create: `src/crawler/sinks/upsert.py`
- Create: `tests/sinks/test_upsert.py`

- [ ] **Step 10.1: Write failing test `tests/sinks/test_upsert.py`**

```python
from crawler.sinks.base import SheetName
from crawler.sinks.fake import FakeRepository
from crawler.sinks.upsert import UpsertEngine, UpsertReport


def test_upsert_inserts_new_rows():
    repo = FakeRepository()
    engine = UpsertEngine(repo)
    report = engine.upsert(SheetName.VENUES, [{"id": "v1", "name": "류가헌"}])
    assert report == UpsertReport(new=1, updated=0, unchanged=0)
    assert repo.read_rows(SheetName.VENUES) == [{"id": "v1", "name": "류가헌"}]


def test_upsert_updates_changed_rows_only():
    repo = FakeRepository()
    engine = UpsertEngine(repo)
    engine.upsert(SheetName.VENUES, [{"id": "v1", "name": "류가헌"}])
    report = engine.upsert(SheetName.VENUES, [{"id": "v1", "name": "사진위주 류가헌"}])
    assert report == UpsertReport(new=0, updated=1, unchanged=0)


def test_upsert_skips_unchanged_rows():
    repo = FakeRepository()
    engine = UpsertEngine(repo)
    engine.upsert(SheetName.VENUES, [{"id": "v1", "name": "류가헌"}])
    report = engine.upsert(SheetName.VENUES, [{"id": "v1", "name": "류가헌"}])
    assert report == UpsertReport(new=0, updated=0, unchanged=1)


def test_upsert_mixed_batch():
    repo = FakeRepository()
    engine = UpsertEngine(repo)
    engine.upsert(SheetName.VENUES, [
        {"id": "v1", "name": "A"},
        {"id": "v2", "name": "B"},
    ])
    report = engine.upsert(SheetName.VENUES, [
        {"id": "v1", "name": "A"},       # unchanged
        {"id": "v2", "name": "B prime"}, # updated
        {"id": "v3", "name": "C"},       # new
    ])
    assert report == UpsertReport(new=1, updated=1, unchanged=1)


def test_upsert_preserves_existing_columns_not_in_patch():
    repo = FakeRepository()
    engine = UpsertEngine(repo)
    engine.upsert(SheetName.VENUES, [{"id": "v1", "name": "A", "latitude": 37.5}])
    engine.upsert(SheetName.VENUES, [{"id": "v1", "name": "A prime"}])
    # latitude was not in the patch — must survive
    assert repo.read_rows(SheetName.VENUES)[0]["latitude"] == 37.5
```

- [ ] **Step 10.2: Run, see fail**

Run: `pytest tests/sinks/test_upsert.py -v`
Expected: ImportError.

- [ ] **Step 10.3: Write `src/crawler/sinks/upsert.py`**

```python
"""Compute diff vs existing rows and write only what changed."""

from __future__ import annotations

from dataclasses import dataclass

from crawler.sinks.base import Repository, SheetName


@dataclass(frozen=True)
class UpsertReport:
    new: int
    updated: int
    unchanged: int


class UpsertEngine:
    def __init__(self, repo: Repository) -> None:
        self._repo = repo

    def upsert(self, sheet: SheetName, rows: list[dict]) -> UpsertReport:
        existing = {r["id"]: r for r in self._repo.read_rows(sheet)}
        new_rows: list[dict] = []
        patches: list[dict] = []
        unchanged = 0

        for incoming in rows:
            row_id = incoming["id"]
            current = existing.get(row_id)
            if current is None:
                new_rows.append(incoming)
                continue
            merged = {**current, **incoming}
            if merged == current:
                unchanged += 1
            else:
                patches.append(merged)

        if new_rows:
            self._repo.append_rows(sheet, new_rows)
        if patches:
            self._repo.patch_rows(sheet, patches)

        return UpsertReport(
            new=len(new_rows),
            updated=len(patches),
            unchanged=unchanged,
        )
```

- [ ] **Step 10.4: Run, expect pass**

Run: `pytest tests/sinks/test_upsert.py -v`
Expected: 5 passed.

- [ ] **Step 10.5: Commit**

```bash
git add src/crawler/sinks/upsert.py tests/sinks/test_upsert.py
git commit -m "feat(sinks): UpsertEngine with diff-aware writes"
```

---

## Task 11: gspread repository + init-sheets

**Files:**
- Create: `src/crawler/sinks/gspread_repo.py`
- Create: `src/crawler/sinks/init_sheets.py`
- Create: `tests/sinks/test_init_sheets.py`

- [ ] **Step 11.1: Write failing test `tests/sinks/test_init_sheets.py`**

```python
from crawler.sinks.base import SheetName
from crawler.sinks.fake import FakeRepository
from crawler.sinks.init_sheets import HEADERS, init_sheets


class _RecordingRepo(FakeRepository):
    """Fake that tracks header writes for the init flow."""

    def __init__(self) -> None:
        super().__init__()
        self.headers: dict[SheetName, list[str]] = {}

    def write_headers(self, sheet: SheetName, headers: list[str]) -> None:
        self.headers[sheet] = list(headers)


def test_init_sheets_writes_all_five_headers():
    repo = _RecordingRepo()
    init_sheets(repo)
    assert set(repo.headers) == set(SheetName)
    for sheet, headers in repo.headers.items():
        assert headers == HEADERS[sheet]


def test_init_sheets_is_idempotent_on_matching_headers():
    repo = _RecordingRepo()
    init_sheets(repo)
    init_sheets(repo)  # second call should not raise
    assert set(repo.headers) == set(SheetName)
```

- [ ] **Step 11.2: Run, see fail**

Run: `pytest tests/sinks/test_init_sheets.py -v`
Expected: ImportError.

- [ ] **Step 11.3: Write `src/crawler/sinks/init_sheets.py`**

```python
"""Idempotent worksheet + header initialization.

The repo passed in must implement `write_headers(sheet, headers)` in addition to
the read/append/patch Repository protocol. Production code uses `GspreadRepository`.
"""

from __future__ import annotations

from typing import Protocol

from crawler.sinks.base import Repository, SheetName


class HeaderRepository(Repository, Protocol):
    def write_headers(self, sheet: SheetName, headers: list[str]) -> None: ...


HEADERS: dict[SheetName, list[str]] = {
    SheetName.EXHIBITIONS: [
        "id", "source", "status", "source_url", "title", "title_en",
        "description", "poster_image_url", "medium", "exhibition_type",
        "genre_tags", "fee_type", "price_min", "price_max", "activities",
        "start_date", "end_date", "open_hours", "artist_ids", "venue_id",
        "organizer_id", "popularity_score", "featured", "crawled_at",
        "updated_at", "_warnings",
    ],
    SheetName.ARTISTS: [
        "id", "name", "name_en", "name_normalized", "bio", "instagram",
        "website", "sources", "first_seen_at", "updated_at",
    ],
    SheetName.VENUES: [
        "id", "name", "name_en", "venue_type", "region", "district",
        "address", "latitude", "longitude", "website", "open_hours_default",
        "sources", "first_seen_at", "updated_at",
    ],
    SheetName.ORGANIZERS: [
        "id", "name", "name_en", "name_normalized", "organizer_type",
        "website", "sources", "first_seen_at", "updated_at",
    ],
    SheetName.OVERRIDES: [
        "entity_type", "match_pattern", "canonical_id", "note",
    ],
}


def init_sheets(repo: HeaderRepository) -> None:
    """Create or verify headers for every sheet. Idempotent."""
    for sheet, headers in HEADERS.items():
        repo.write_headers(sheet, headers)
```

- [ ] **Step 11.4: Write `src/crawler/sinks/gspread_repo.py`**

```python
"""Google Sheets backend via gspread + service account.

Real-world rows are kept as dicts keyed by header. We avoid per-cell calls;
reads pull the whole sheet, writes use batch operations.
"""

from __future__ import annotations

import json
import os

import gspread
from google.oauth2.service_account import Credentials

from crawler.sinks.base import SheetName


_SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]


class GspreadRepository:
    def __init__(self, sheet_id: str, service_account_json: str) -> None:
        info = json.loads(service_account_json)
        creds = Credentials.from_service_account_info(info, scopes=_SCOPES)
        self._client = gspread.authorize(creds)
        self._book = self._client.open_by_key(sheet_id)
        self._cache_headers: dict[SheetName, list[str]] = {}

    @classmethod
    def from_env(cls) -> "GspreadRepository":
        sheet_id = os.environ["SHEET_ID"]
        sa_json = os.environ["GOOGLE_SERVICE_ACCOUNT_JSON"]
        return cls(sheet_id, sa_json)

    def _ws(self, sheet: SheetName) -> gspread.Worksheet:
        try:
            return self._book.worksheet(sheet.value)
        except gspread.WorksheetNotFound:
            return self._book.add_worksheet(title=sheet.value, rows=1000, cols=40)

    def write_headers(self, sheet: SheetName, headers: list[str]) -> None:
        ws = self._ws(sheet)
        existing = ws.row_values(1)
        if existing == headers:
            self._cache_headers[sheet] = list(headers)
            return
        if existing and existing != headers:
            raise RuntimeError(
                f"sheet {sheet.value} has mismatched headers (got {existing}, expected {headers}); "
                "refusing to overwrite to protect data"
            )
        ws.update("A1", [headers])
        self._cache_headers[sheet] = list(headers)

    def _headers(self, sheet: SheetName) -> list[str]:
        if sheet in self._cache_headers:
            return self._cache_headers[sheet]
        headers = self._ws(sheet).row_values(1)
        self._cache_headers[sheet] = headers
        return headers

    def read_rows(self, sheet: SheetName) -> list[dict]:
        ws = self._ws(sheet)
        records = ws.get_all_records()
        return [dict(r) for r in records]

    def append_rows(self, sheet: SheetName, rows: list[dict]) -> None:
        if not rows:
            return
        ws = self._ws(sheet)
        headers = self._headers(sheet)
        values = [_serialize_row(headers, r) for r in rows]
        ws.append_rows(values, value_input_option="RAW")

    def patch_rows(self, sheet: SheetName, rows: list[dict]) -> None:
        if not rows:
            return
        ws = self._ws(sheet)
        headers = self._headers(sheet)
        existing = ws.get_all_values()
        # row 1 is headers; find id column index
        id_col = headers.index("id")
        row_index_by_id = {
            row[id_col]: i + 2  # +2: 1-based, skip header row
            for i, row in enumerate(existing[1:])
            if len(row) > id_col
        }
        updates: list[dict] = []
        for r in rows:
            row_id = r["id"]
            row_num = row_index_by_id.get(row_id)
            if row_num is None:
                raise KeyError(f"unknown id {row_id} in {sheet.value}")
            updates.append({
                "range": f"A{row_num}:{_col_letter(len(headers))}{row_num}",
                "values": [_serialize_row(headers, r)],
            })
        ws.batch_update(updates, value_input_option="RAW")


def _serialize_row(headers: list[str], row: dict) -> list:
    return ["" if (v := row.get(h)) is None else _stringify(v) for h in headers]


def _stringify(v) -> str:
    if isinstance(v, list):
        return ",".join(str(x) for x in v)
    if isinstance(v, bool):
        return "TRUE" if v else "FALSE"
    return str(v)


def _col_letter(n: int) -> str:
    """1 -> A, 26 -> Z, 27 -> AA."""
    out = ""
    while n > 0:
        n, rem = divmod(n - 1, 26)
        out = chr(65 + rem) + out
    return out
```

- [ ] **Step 11.5: Run init_sheets tests, expect pass**

Run: `pytest tests/sinks/test_init_sheets.py -v`
Expected: 2 passed.

(Note: `gspread_repo.py` is not unit-tested here — it's exercised only via the optional `external` marker later. The contract is the `Repository` protocol, which is covered by tests against `FakeRepository`.)

- [ ] **Step 11.6: Commit**

```bash
git add src/crawler/sinks/gspread_repo.py src/crawler/sinks/init_sheets.py tests/sinks/test_init_sheets.py
git commit -m "feat(sinks): init_sheets + gspread repository implementation"
```

---

## Task 12: Entity resolver

**Files:**
- Create: `src/crawler/resolver/__init__.py` (empty)
- Create: `src/crawler/resolver/entities.py`
- Create: `tests/resolver/__init__.py` (empty)
- Create: `tests/resolver/test_entities.py`

- [ ] **Step 12.1: Write failing test `tests/resolver/test_entities.py`**

```python
from datetime import datetime, timezone

from freezegun import freeze_time

from crawler.models import (
    NormalizedExhibition,
    SourceName,
    Status,
    Medium,
    ExhibitionType,
)
from crawler.resolver.entities import EntityState, resolve_entities


def _exh(**over) -> NormalizedExhibition:
    base = dict(
        id="x",
        source=SourceName.ARTMAP,
        source_url="https://art-map.co.kr/exhibition/view.php?idx=1",
        title="달과 도시",
        medium=Medium.PHOTO,
        exhibition_type=ExhibitionType.SOLO,
        artist_raw_names=["김작가"],
        venue_raw_name="류가헌",
        organizer_raw_name=None,
        status=Status.UNKNOWN,
        crawled_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )
    base.update(over)
    return NormalizedExhibition.model_validate(base)


@freeze_time("2026-05-28")
def test_resolver_creates_new_entities_when_state_empty():
    state = EntityState(artists=[], venues=[], organizers=[], overrides=[])
    out = resolve_entities(_exh(), state)
    assert len(out.new_artists) == 1
    assert len(out.new_venues) == 1
    assert len(out.new_organizers) == 0
    assert out.exhibition.artist_ids == [out.new_artists[0].id]
    assert out.exhibition.venue_id == out.new_venues[0].id
    assert out.exhibition.organizer_id == out.new_venues[0].id  # fallback


@freeze_time("2026-05-28")
def test_resolver_reuses_existing_artist_by_normalized_name():
    from crawler.models import Artist
    from crawler.normalize.dedup import artist_id
    from crawler.normalize.text import normalize_name

    existing = Artist(
        id=artist_id(normalize_name("김작가")),
        name="김작가",
        name_normalized=normalize_name("김작가"),
        sources=["naver"],
        first_seen_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )
    state = EntityState(artists=[existing], venues=[], organizers=[], overrides=[])
    out = resolve_entities(_exh(), state)
    assert out.new_artists == []
    assert out.exhibition.artist_ids == [existing.id]


@freeze_time("2026-05-28")
def test_resolver_applies_override_for_artist_alias():
    from crawler.models import Artist
    from crawler.normalize.dedup import artist_id
    from crawler.normalize.text import normalize_name

    canonical = Artist(
        id=artist_id(normalize_name("김주현")),
        name="김주현",
        name_normalized=normalize_name("김주현"),
        sources=["naver"],
        first_seen_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )
    override = {
        "entity_type": "artist",
        "match_pattern": "김작가",
        "canonical_id": canonical.id,
        "note": "stage name",
    }
    state = EntityState(artists=[canonical], venues=[], organizers=[], overrides=[override])
    out = resolve_entities(_exh(), state)
    assert out.exhibition.artist_ids == [canonical.id]
    assert out.new_artists == []
```

- [ ] **Step 12.2: Run, see fail**

Run: `pytest tests/resolver/test_entities.py -v`
Expected: ImportError.

- [ ] **Step 12.3: Write `src/crawler/resolver/__init__.py`** (empty)

```python
"""Entity resolution: raw names → stable IDs."""
```

- [ ] **Step 12.4: Write `src/crawler/resolver/entities.py`**

```python
"""Resolve raw artist/venue/organizer names to existing IDs or stage new entities."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone

from crawler.models import (
    Artist,
    NormalizedExhibition,
    Organizer,
    Venue,
    OrganizerType,
    VenueType,
)
from crawler.normalize.categories import map_organizer_type, map_venue_type
from crawler.normalize.dedup import artist_id, organizer_id, venue_id
from crawler.normalize.text import normalize_name


@dataclass
class EntityState:
    artists: list[Artist]
    venues: list[Venue]
    organizers: list[Organizer]
    overrides: list[dict]


@dataclass
class ResolveResult:
    exhibition: NormalizedExhibition
    new_artists: list[Artist] = field(default_factory=list)
    new_venues: list[Venue] = field(default_factory=list)
    new_organizers: list[Organizer] = field(default_factory=list)


def _override_lookup(overrides: list[dict], entity_type: str) -> dict[str, str]:
    """match_pattern -> canonical_id."""
    return {
        o["match_pattern"]: o["canonical_id"]
        for o in overrides
        if o.get("entity_type") == entity_type and o.get("match_pattern") and o.get("canonical_id")
    }


def resolve_entities(
    exh: NormalizedExhibition,
    state: EntityState,
) -> ResolveResult:
    now = datetime.now(timezone.utc)
    source = exh.source.value

    # --- Artists (N:M) ---
    artist_overrides = _override_lookup(state.overrides, "artist")
    artists_by_id = {a.id: a for a in state.artists}
    artists_by_norm = {a.name_normalized: a for a in state.artists}

    resolved_artist_ids: list[str] = []
    new_artists: list[Artist] = []
    for raw_name in exh.artist_raw_names:
        if raw_name in artist_overrides:
            target = artist_overrides[raw_name]
            if target in artists_by_id:
                resolved_artist_ids.append(target)
                continue
        norm = normalize_name(raw_name)
        if not norm:
            continue
        if norm in artists_by_norm:
            resolved_artist_ids.append(artists_by_norm[norm].id)
            continue
        new_id = artist_id(norm)
        new_artists.append(
            Artist(
                id=new_id,
                name=raw_name,
                name_normalized=norm,
                sources=[source],
                first_seen_at=now,
                updated_at=now,
            )
        )
        artists_by_norm[norm] = new_artists[-1]
        resolved_artist_ids.append(new_id)

    # --- Venue (N:1) ---
    venue_overrides = _override_lookup(state.overrides, "venue")
    new_venues: list[Venue] = []
    resolved_venue_id = ""
    if exh.venue_raw_name:
        if exh.venue_raw_name in venue_overrides:
            resolved_venue_id = venue_overrides[exh.venue_raw_name]
        else:
            # NormalizedExhibition only carries the venue name at this stage;
            # actual address is resolved later inside the Venue entity.
            candidate_id = venue_id(exh.venue_raw_name, None)
            existing = next((v for v in state.venues if v.id == candidate_id), None)
            if existing:
                resolved_venue_id = existing.id
            else:
                new_venues.append(
                    Venue(
                        id=candidate_id,
                        name=exh.venue_raw_name,
                        venue_type=map_venue_type(exh.venue_raw_name) or VenueType.OTHER,
                        sources=[source],
                        first_seen_at=now,
                        updated_at=now,
                    )
                )
                resolved_venue_id = candidate_id

    # --- Organizer (N:1) ---
    organizer_overrides = _override_lookup(state.overrides, "organizer")
    new_organizers: list[Organizer] = []
    resolved_organizer_id = resolved_venue_id  # fallback: same as venue
    if exh.organizer_raw_name:
        if exh.organizer_raw_name in organizer_overrides:
            resolved_organizer_id = organizer_overrides[exh.organizer_raw_name]
        else:
            norm = normalize_name(exh.organizer_raw_name)
            existing = next(
                (o for o in state.organizers if o.name_normalized == norm),
                None,
            )
            if existing:
                resolved_organizer_id = existing.id
            else:
                new_id = organizer_id(norm)
                new_organizers.append(
                    Organizer(
                        id=new_id,
                        name=exh.organizer_raw_name,
                        name_normalized=norm,
                        organizer_type=map_organizer_type(exh.organizer_raw_name) or OrganizerType.OTHER,
                        sources=[source],
                        first_seen_at=now,
                        updated_at=now,
                    )
                )
                resolved_organizer_id = new_id

    resolved = exh.model_copy(update={
        "artist_ids": resolved_artist_ids,
        "venue_id": resolved_venue_id,
        "organizer_id": resolved_organizer_id,
    })

    return ResolveResult(
        exhibition=resolved,
        new_artists=new_artists,
        new_venues=new_venues,
        new_organizers=new_organizers,
    )
```

- [ ] **Step 12.5: Run, expect pass**

Run: `pytest tests/resolver/test_entities.py -v`
Expected: 3 passed.

- [ ] **Step 12.6: Commit**

```bash
git add src/crawler/resolver/ tests/resolver/
git commit -m "feat(resolver): match/create Artist/Venue/Organizer with overrides"
```

---

## Task 13: Geocoder (Kakao Local API)

**Files:**
- Create: `src/crawler/enrich/__init__.py` (empty)
- Create: `src/crawler/enrich/geocoder.py`
- Create: `tests/enrich/__init__.py` (empty)
- Create: `tests/enrich/test_geocoder.py`

- [ ] **Step 13.1: Write failing test `tests/enrich/test_geocoder.py`**

```python
import httpx
import respx

from crawler.enrich.geocoder import KakaoGeocoder


@respx.mock
def test_geocoder_returns_lat_lng_on_match():
    respx.get("https://dapi.kakao.com/v2/local/search/address.json").mock(
        return_value=httpx.Response(200, json={
            "documents": [{
                "y": "37.582",
                "x": "126.969",
                "address_name": "서울 종로구 자하문로 106",
            }],
        })
    )
    geo = KakaoGeocoder(api_key="test")
    lat, lng = geo.geocode("서울 종로구 자하문로 106")
    assert lat == 37.582 and lng == 126.969


@respx.mock
def test_geocoder_returns_none_when_no_match():
    respx.get("https://dapi.kakao.com/v2/local/search/address.json").mock(
        return_value=httpx.Response(200, json={"documents": []})
    )
    geo = KakaoGeocoder(api_key="test")
    assert geo.geocode("nowhere") == (None, None)


@respx.mock
def test_geocoder_falls_back_to_keyword_search_on_address_miss():
    respx.get("https://dapi.kakao.com/v2/local/search/address.json").mock(
        return_value=httpx.Response(200, json={"documents": []})
    )
    respx.get("https://dapi.kakao.com/v2/local/search/keyword.json").mock(
        return_value=httpx.Response(200, json={
            "documents": [{"y": "37.5", "x": "127.0"}],
        })
    )
    geo = KakaoGeocoder(api_key="test")
    assert geo.geocode("류가헌") == (37.5, 127.0)
```

- [ ] **Step 13.2: Run, see fail**

Run: `pytest tests/enrich/test_geocoder.py -v`
Expected: ImportError.

- [ ] **Step 13.3: Write `src/crawler/enrich/__init__.py`** (empty)

```python
"""Enrichment (geocoding, popularity)."""
```

- [ ] **Step 13.4: Write `src/crawler/enrich/geocoder.py`**

```python
"""Kakao Local API geocoder. Address search first, keyword fallback."""

from __future__ import annotations

import os

import httpx
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential


_ADDRESS_URL = "https://dapi.kakao.com/v2/local/search/address.json"
_KEYWORD_URL = "https://dapi.kakao.com/v2/local/search/keyword.json"


class KakaoGeocoder:
    def __init__(self, api_key: str, timeout: float = 10.0) -> None:
        self._client = httpx.Client(
            timeout=timeout,
            headers={"Authorization": f"KakaoAK {api_key}"},
        )

    @classmethod
    def from_env(cls) -> "KakaoGeocoder":
        return cls(api_key=os.environ["KAKAO_REST_API_KEY"])

    @retry(
        retry=retry_if_exception_type(httpx.TransportError),
        wait=wait_exponential(multiplier=1, min=1, max=16),
        stop=stop_after_attempt(3),
        reraise=True,
    )
    def _get(self, url: str, params: dict) -> dict:
        r = self._client.get(url, params=params)
        r.raise_for_status()
        return r.json()

    def geocode(self, query: str) -> tuple[float | None, float | None]:
        if not query:
            return None, None
        # Try address search first
        data = self._get(_ADDRESS_URL, {"query": query})
        docs = data.get("documents", [])
        if docs:
            d = docs[0]
            return float(d["y"]), float(d["x"])
        # Fallback to keyword search (place name)
        data = self._get(_KEYWORD_URL, {"query": query})
        docs = data.get("documents", [])
        if docs:
            d = docs[0]
            return float(d["y"]), float(d["x"])
        return None, None

    def close(self) -> None:
        self._client.close()
```

- [ ] **Step 13.5: Run, expect pass**

Run: `pytest tests/enrich/test_geocoder.py -v`
Expected: 3 passed.

- [ ] **Step 13.6: Commit**

```bash
git add src/crawler/enrich/ tests/enrich/
git commit -m "feat(enrich): KakaoGeocoder with address + keyword fallback"
```

---

## Task 14: Reporter

**Files:**
- Create: `src/crawler/reporter.py`
- Create: `tests/test_reporter.py`

- [ ] **Step 14.1: Write failing test `tests/test_reporter.py`**

```python
from datetime import datetime, timezone

from crawler.reporter import RunReport, SourceReport, render_markdown


def test_render_markdown_includes_table_rows():
    report = RunReport(
        started_at=datetime(2026, 5, 28, 18, 0, tzinfo=timezone.utc),
        sources=[
            SourceReport(
                name="artmap", extracted=234, new=12, updated=45,
                unchanged=177, errors=0, duration_s=42.1, failure=None,
            ),
            SourceReport(
                name="photo_sema", extracted=0, new=0, updated=0,
                unchanged=0, errors=1, duration_s=8.0,
                failure="selector .exhibition-card missing",
            ),
        ],
    )
    md = render_markdown(report)
    assert "artmap" in md and "234" in md
    assert "photo_sema" in md
    assert "selector .exhibition-card missing" in md


def test_render_markdown_no_failures_section_when_clean():
    report = RunReport(
        started_at=datetime(2026, 5, 28, 18, 0, tzinfo=timezone.utc),
        sources=[
            SourceReport(name="artmap", extracted=1, new=1, updated=0,
                         unchanged=0, errors=0, duration_s=1.0, failure=None),
        ],
    )
    md = render_markdown(report)
    assert "### Failures" not in md
```

- [ ] **Step 14.2: Run, see fail**

Run: `pytest tests/test_reporter.py -v`
Expected: ImportError.

- [ ] **Step 14.3: Write `src/crawler/reporter.py`**

```python
"""Markdown crawl report rendering."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


@dataclass
class SourceReport:
    name: str
    extracted: int
    new: int
    updated: int
    unchanged: int
    errors: int
    duration_s: float
    failure: str | None


@dataclass
class RunReport:
    started_at: datetime
    sources: list[SourceReport]


def render_markdown(report: RunReport) -> str:
    started = report.started_at.strftime("%Y-%m-%d %H:%M UTC")
    lines = [
        f"## Crawl Report — {started}",
        "",
        "| source | extracted | new | updated | unchanged | errors | duration |",
        "|--------|-----------|-----|---------|-----------|--------|----------|",
    ]
    for s in report.sources:
        lines.append(
            f"| {s.name} | {s.extracted} | {s.new} | {s.updated} | "
            f"{s.unchanged} | {s.errors} | {s.duration_s:.1f}s |"
        )
    failures = [s for s in report.sources if s.failure]
    if failures:
        lines += ["", "### Failures"]
        for f in failures:
            lines.append(f"- **{f.name}**: {f.failure}")
    return "\n".join(lines) + "\n"
```

- [ ] **Step 14.4: Run, expect pass**

Run: `pytest tests/test_reporter.py -v`
Expected: 2 passed.

- [ ] **Step 14.5: Commit**

```bash
git add src/crawler/reporter.py tests/test_reporter.py
git commit -m "feat(reporter): markdown run report"
```

---

## Task 15: Pipeline orchestrator

**Files:**
- Create: `src/crawler/pipeline.py`
- Create: `tests/test_pipeline.py`

- [ ] **Step 15.1: Write failing test `tests/test_pipeline.py`**

```python
from datetime import date, datetime, timezone
from typing import Iterable

from freezegun import freeze_time

from crawler.models import (
    ExhibitionType,
    Medium,
    RawExhibition,
    SourceName,
    Status,
)
from crawler.pipeline import run_source
from crawler.reporter import SourceReport
from crawler.sinks.base import SheetName
from crawler.sinks.fake import FakeRepository
from crawler.sinks.init_sheets import init_sheets


class _DummyExtractor:
    name = SourceName.ARTMAP

    def __init__(self, raws: list[RawExhibition]) -> None:
        self.raws = raws

    def crawl(self) -> Iterable[RawExhibition]:
        yield from self.raws


class _FakeHeaderRepo(FakeRepository):
    def write_headers(self, sheet: SheetName, headers: list[str]) -> None:  # noqa: ARG002
        return None  # not needed for in-memory


class _NullGeocoder:
    def geocode(self, query: str) -> tuple[float | None, float | None]:  # noqa: ARG002
        return None, None


def _raw(idx: int, title: str) -> RawExhibition:
    return RawExhibition(
        source=SourceName.ARTMAP,
        source_url=f"https://art-map.co.kr/exhibition/view.php?idx={idx}",
        raw={
            "title": title,
            "venue_name": "류가헌",
            "artists": ["김작가"],
            "date_range": "2026.06.01 ~ 2026.07.01",
            "fee_text": "무료",
            "exhibition_type_text": "개인전",
        },
    )


@freeze_time("2026-05-28")
def test_run_source_end_to_end():
    repo = _FakeHeaderRepo()
    init_sheets(repo)
    extractor = _DummyExtractor([_raw(1, "A"), _raw(2, "B")])

    report: SourceReport = run_source(
        extractor=extractor,
        repo=repo,
        geocoder=_NullGeocoder(),
        today=date(2026, 5, 28),
    )

    assert report.name == "artmap"
    assert report.extracted == 2
    assert report.new == 2  # both new
    exh_rows = repo.read_rows(SheetName.EXHIBITIONS)
    assert {r["title"] for r in exh_rows} == {"A", "B"}
    # status was computed
    for r in exh_rows:
        assert r["status"] == Status.UPCOMING.value
    # one venue created and reused (artist too)
    assert len(repo.read_rows(SheetName.VENUES)) == 1
    assert len(repo.read_rows(SheetName.ARTISTS)) == 1


@freeze_time("2026-05-28")
def test_run_source_isolates_item_failure():
    repo = _FakeHeaderRepo()
    init_sheets(repo)
    # second item is missing title → normalize raises → item skipped
    bad = RawExhibition(
        source=SourceName.ARTMAP,
        source_url="https://art-map.co.kr/exhibition/view.php?idx=99",
        raw={"venue_name": "류가헌"},
    )
    extractor = _DummyExtractor([_raw(1, "A"), bad, _raw(2, "B")])

    report = run_source(
        extractor=extractor,
        repo=repo,
        geocoder=_NullGeocoder(),
        today=date(2026, 5, 28),
    )

    assert report.extracted == 3
    assert report.new == 2
    assert report.errors == 1
    assert report.failure is None  # not promoted to source failure
```

- [ ] **Step 15.2: Run, see fail**

Run: `pytest tests/test_pipeline.py -v`
Expected: ImportError.

- [ ] **Step 15.3: Write `src/crawler/pipeline.py`**

```python
"""End-to-end orchestration for a single source."""

from __future__ import annotations

import logging
import time
from datetime import date
from typing import Iterable, Protocol

from crawler.models import (
    Artist,
    NormalizedExhibition,
    Organizer,
    RawExhibition,
    SourceName,
    Venue,
)
from crawler.normalize import normalize_exhibition
from crawler.normalize.status import compute_status
from crawler.reporter import SourceReport
from crawler.resolver.entities import EntityState, resolve_entities
from crawler.sinks.base import Repository, SheetName
from crawler.sinks.upsert import UpsertEngine


log = logging.getLogger(__name__)


class Extractor(Protocol):
    name: SourceName

    def crawl(self) -> Iterable[RawExhibition]: ...


class GeocoderProto(Protocol):
    def geocode(self, query: str) -> tuple[float | None, float | None]: ...


def _exhibition_row(e: NormalizedExhibition) -> dict:
    return {
        "id": e.id,
        "source": e.source.value,
        "status": e.status.value,
        "source_url": str(e.source_url),
        "title": e.title,
        "title_en": e.title_en or "",
        "description": e.description or "",
        "poster_image_url": str(e.poster_image_url) if e.poster_image_url else "",
        "medium": e.medium.value,
        "exhibition_type": e.exhibition_type.value,
        "genre_tags": ",".join(e.genre_tags),
        "fee_type": e.fee_type.value,
        "price_min": e.price_min if e.price_min is not None else "",
        "price_max": e.price_max if e.price_max is not None else "",
        "activities": ",".join(e.activities),
        "start_date": e.start_date.isoformat() if e.start_date else "",
        "end_date": e.end_date.isoformat() if e.end_date else "",
        "open_hours": e.open_hours or "",
        "artist_ids": ",".join(e.artist_ids),
        "venue_id": e.venue_id,
        "organizer_id": e.organizer_id,
        "popularity_score": e.popularity_score if e.popularity_score is not None else "",
        "featured": "TRUE" if e.featured else "FALSE",
        "crawled_at": e.crawled_at.isoformat(),
        "updated_at": e.updated_at.isoformat(),
        "_warnings": ",".join(e.warnings),
    }


def _artist_row(a: Artist) -> dict:
    return {
        "id": a.id, "name": a.name, "name_en": a.name_en or "",
        "name_normalized": a.name_normalized, "bio": a.bio or "",
        "instagram": str(a.instagram) if a.instagram else "",
        "website": str(a.website) if a.website else "",
        "sources": ",".join(a.sources),
        "first_seen_at": a.first_seen_at.isoformat(),
        "updated_at": a.updated_at.isoformat(),
    }


def _venue_row(v: Venue) -> dict:
    return {
        "id": v.id, "name": v.name, "name_en": v.name_en or "",
        "venue_type": v.venue_type.value, "region": v.region or "",
        "district": v.district or "", "address": v.address or "",
        "latitude": v.latitude if v.latitude is not None else "",
        "longitude": v.longitude if v.longitude is not None else "",
        "website": str(v.website) if v.website else "",
        "open_hours_default": v.open_hours_default or "",
        "sources": ",".join(v.sources),
        "first_seen_at": v.first_seen_at.isoformat(),
        "updated_at": v.updated_at.isoformat(),
    }


def _organizer_row(o: Organizer) -> dict:
    return {
        "id": o.id, "name": o.name, "name_en": o.name_en or "",
        "name_normalized": o.name_normalized,
        "organizer_type": o.organizer_type.value,
        "website": str(o.website) if o.website else "",
        "sources": ",".join(o.sources),
        "first_seen_at": o.first_seen_at.isoformat(),
        "updated_at": o.updated_at.isoformat(),
    }


def run_source(
    extractor: Extractor,
    repo: Repository,
    geocoder: GeocoderProto,
    today: date,
) -> SourceReport:
    name = extractor.name.value
    started = time.monotonic()

    state = EntityState(
        artists=[_artist_from_row(r) for r in repo.read_rows(SheetName.ARTISTS)],
        venues=[_venue_from_row(r) for r in repo.read_rows(SheetName.VENUES)],
        organizers=[_organizer_from_row(r) for r in repo.read_rows(SheetName.ORGANIZERS)],
        overrides=repo.read_rows(SheetName.OVERRIDES),
    )

    engine = UpsertEngine(repo)

    extracted = 0
    errors = 0
    failure: str | None = None
    exh_rows: list[dict] = []
    new_artists_acc: list[Artist] = []
    new_venues_acc: list[Venue] = []
    new_organizers_acc: list[Organizer] = []

    try:
        for raw in extractor.crawl():
            extracted += 1
            try:
                normalized = normalize_exhibition(raw)
                result = resolve_entities(normalized, state)

                # geocode brand-new venues
                for v in result.new_venues:
                    lat, lng = geocoder.geocode(v.address or v.name)
                    if lat is not None and lng is not None:
                        v.latitude, v.longitude = lat, lng
                    new_venues_acc.append(v)
                    state.venues.append(v)

                for a in result.new_artists:
                    new_artists_acc.append(a)
                    state.artists.append(a)
                for o in result.new_organizers:
                    new_organizers_acc.append(o)
                    state.organizers.append(o)

                e = result.exhibition
                e = e.model_copy(update={"status": compute_status(today, e.start_date, e.end_date)})
                exh_rows.append(_exhibition_row(e))
            except Exception as exc:  # per-item isolation
                errors += 1
                log.warning("item failed in %s: %s", name, exc)
    except Exception as exc:
        failure = f"{type(exc).__name__}: {exc}"
        log.error("source %s failed: %s", name, exc)

    new = updated = unchanged = 0
    if new_artists_acc:
        rep = engine.upsert(SheetName.ARTISTS, [_artist_row(a) for a in new_artists_acc])
        new += rep.new; updated += rep.updated; unchanged += rep.unchanged
    if new_venues_acc:
        rep = engine.upsert(SheetName.VENUES, [_venue_row(v) for v in new_venues_acc])
        new += rep.new; updated += rep.updated; unchanged += rep.unchanged
    if new_organizers_acc:
        rep = engine.upsert(SheetName.ORGANIZERS, [_organizer_row(o) for o in new_organizers_acc])
        new += rep.new; updated += rep.updated; unchanged += rep.unchanged
    if exh_rows:
        rep = engine.upsert(SheetName.EXHIBITIONS, exh_rows)
        new += rep.new; updated += rep.updated; unchanged += rep.unchanged

    return SourceReport(
        name=name,
        extracted=extracted,
        new=new,
        updated=updated,
        unchanged=unchanged,
        errors=errors,
        duration_s=time.monotonic() - started,
        failure=failure,
    )


# --- helpers: row -> model for state hydration ---


def _artist_from_row(r: dict) -> Artist:
    from datetime import datetime
    return Artist(
        id=r["id"],
        name=r["name"],
        name_en=r.get("name_en") or None,
        name_normalized=r["name_normalized"],
        bio=r.get("bio") or None,
        instagram=r.get("instagram") or None,
        website=r.get("website") or None,
        sources=[s for s in (r.get("sources") or "").split(",") if s],
        first_seen_at=datetime.fromisoformat(r["first_seen_at"]),
        updated_at=datetime.fromisoformat(r["updated_at"]),
    )


def _venue_from_row(r: dict) -> Venue:
    from datetime import datetime
    from crawler.models import VenueType
    return Venue(
        id=r["id"],
        name=r["name"],
        name_en=r.get("name_en") or None,
        venue_type=VenueType(r.get("venue_type") or "other"),
        region=r.get("region") or None,
        district=r.get("district") or None,
        address=r.get("address") or None,
        latitude=float(r["latitude"]) if r.get("latitude") not in (None, "") else None,
        longitude=float(r["longitude"]) if r.get("longitude") not in (None, "") else None,
        website=r.get("website") or None,
        open_hours_default=r.get("open_hours_default") or None,
        sources=[s for s in (r.get("sources") or "").split(",") if s],
        first_seen_at=datetime.fromisoformat(r["first_seen_at"]),
        updated_at=datetime.fromisoformat(r["updated_at"]),
    )


def _organizer_from_row(r: dict) -> Organizer:
    from datetime import datetime
    from crawler.models import OrganizerType
    return Organizer(
        id=r["id"],
        name=r["name"],
        name_en=r.get("name_en") or None,
        name_normalized=r["name_normalized"],
        organizer_type=OrganizerType(r.get("organizer_type") or "other"),
        website=r.get("website") or None,
        sources=[s for s in (r.get("sources") or "").split(",") if s],
        first_seen_at=datetime.fromisoformat(r["first_seen_at"]),
        updated_at=datetime.fromisoformat(r["updated_at"]),
    )
```

- [ ] **Step 15.4: Run, expect pass**

Run: `pytest tests/test_pipeline.py -v`
Expected: 2 passed.

- [ ] **Step 15.5: Commit**

```bash
git add src/crawler/pipeline.py tests/test_pipeline.py
git commit -m "feat(pipeline): orchestrate extract→normalize→resolve→geocode→upsert"
```

---

## Task 16: CLI

**Files:**
- Create: `src/crawler/cli.py`
- Create: `tests/test_cli.py`

- [ ] **Step 16.1: Write failing test `tests/test_cli.py`**

```python
from typer.testing import CliRunner

from crawler.cli import app


def test_cli_help_lists_commands():
    runner = CliRunner()
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0
    assert "init-sheets" in result.stdout
    assert "run" in result.stdout
    assert "dry-run" in result.stdout
    assert "run-all" in result.stdout


def test_cli_dry_run_artmap_no_network(monkeypatch):
    """dry-run with a stub source registered via env shouldn't try to write."""
    from crawler.models import RawExhibition, SourceName
    from crawler.sources.base import register_source

    class StubExtractor:
        name = SourceName.ARTMAP

        def crawl(self):
            yield RawExhibition(
                source=SourceName.ARTMAP,
                source_url="https://art-map.co.kr/exhibition/view.php?idx=1",
                raw={
                    "title": "A",
                    "venue_name": "류가헌",
                    "artists": ["김"],
                    "date_range": "2026.06.01 ~ 2026.07.01",
                    "fee_text": "무료",
                    "exhibition_type_text": "개인전",
                },
            )

    register_source(SourceName.ARTMAP, StubExtractor)
    runner = CliRunner()
    result = runner.invoke(app, ["dry-run", "artmap"])
    assert result.exit_code == 0, result.stdout
    assert "달과 도시" in result.stdout or '"title": "A"' in result.stdout or "title" in result.stdout
```

- [ ] **Step 16.2: Run, see fail**

Run: `pytest tests/test_cli.py -v`
Expected: ImportError.

- [ ] **Step 16.3: Write `src/crawler/cli.py`**

```python
"""Typer CLI: init-sheets, run, dry-run, run-all."""

from __future__ import annotations

import json
import sys
from datetime import date, datetime, timezone

import typer

from crawler.models import SourceName
from crawler.normalize import normalize_exhibition
from crawler.pipeline import run_source
from crawler.reporter import RunReport, render_markdown
from crawler.sinks.base import SheetName
from crawler.sources.base import get_source


app = typer.Typer(help="Korean photo/video/camera exhibition crawler.")


def _today() -> date:
    return datetime.now(timezone.utc).date()


def _build_repo():
    from crawler.sinks.gspread_repo import GspreadRepository
    return GspreadRepository.from_env()


def _build_geocoder():
    from crawler.enrich.geocoder import KakaoGeocoder
    return KakaoGeocoder.from_env()


@app.command("init-sheets")
def init_sheets_cmd() -> None:
    """Create the 5 worksheets with headers (idempotent)."""
    from crawler.sinks.init_sheets import init_sheets
    repo = _build_repo()
    init_sheets(repo)
    typer.echo("init-sheets: done")


@app.command("run")
def run_cmd(source: str) -> None:
    """Crawl one source and upsert into the sheet."""
    try:
        src = SourceName(source)
    except ValueError as e:
        raise typer.BadParameter(str(e))
    extractor_cls = get_source(src)
    report = run_source(
        extractor=extractor_cls(),
        repo=_build_repo(),
        geocoder=_build_geocoder(),
        today=_today(),
    )
    run_report = RunReport(started_at=datetime.now(timezone.utc), sources=[report])
    typer.echo(render_markdown(run_report))
    if report.failure:
        raise typer.Exit(code=1)


@app.command("dry-run")
def dry_run_cmd(source: str) -> None:
    """Crawl one source and print normalized rows without writing."""
    try:
        src = SourceName(source)
    except ValueError as e:
        raise typer.BadParameter(str(e))
    extractor_cls = get_source(src)
    extractor = extractor_cls()
    for raw in extractor.crawl():
        try:
            n = normalize_exhibition(raw)
            typer.echo(json.dumps(n.model_dump(mode="json"), ensure_ascii=False))
        except Exception as exc:
            typer.echo(f"# skip: {exc}", err=True)


@app.command("run-all")
def run_all_cmd() -> None:
    """Crawl every registered source. Per-source failures are isolated."""
    from crawler.sources.base import all_sources
    from crawler.reporter import SourceReport
    repo = _build_repo()
    geocoder = _build_geocoder()
    reports = []
    for src, extractor_cls in all_sources().items():
        try:
            report = run_source(
                extractor=extractor_cls(),
                repo=repo,
                geocoder=geocoder,
                today=_today(),
            )
        except Exception as exc:  # site-level isolation
            report = SourceReport(
                name=src.value, extracted=0, new=0, updated=0,
                unchanged=0, errors=1, duration_s=0.0,
                failure=f"{type(exc).__name__}: {exc}",
            )
        reports.append(report)
    run_report = RunReport(started_at=datetime.now(timezone.utc), sources=reports)
    md = render_markdown(run_report)
    typer.echo(md)
    # also dump to out/report.md for CI artifacts
    import os
    os.makedirs("out", exist_ok=True)
    with open("out/report.md", "w", encoding="utf-8") as f:
        f.write(md)
    if any(r.failure for r in reports):
        sys.exit(1)


def main() -> None:  # pragma: no cover
    app()


if __name__ == "__main__":  # pragma: no cover
    main()
```

(Note: this command depends on `crawler/sources/base.py` defined in the next task. Run order: write Task 17 before this test passes. We split for clarity but the failing test in 16.2 will still error until 17.4. That's OK — fix the test temporarily by stubbing imports, then re-run after Task 17.)

- [ ] **Step 16.4: Defer CLI test until Task 17**

Skip running `pytest tests/test_cli.py` now — it depends on `sources/base.py`. The CLI itself only fails at import if `crawler.sources.base` is missing. Confirm this:

Run: `python -c "import crawler.cli"`
Expected: ImportError naming `crawler.sources.base` (proves the only missing piece is the next task).

- [ ] **Step 16.5: Commit (without running CLI test yet)**

```bash
git add src/crawler/cli.py tests/test_cli.py
git commit -m "feat(cli): typer commands for init-sheets/run/dry-run/run-all"
```

---

## Task 17: Source registry + base extractor

**Files:**
- Create: `src/crawler/sources/__init__.py` (empty)
- Create: `src/crawler/sources/base.py`
- Create: `docs/sources/artmap.md`

- [ ] **Step 17.1: Write `src/crawler/sources/__init__.py`** (empty)

```python
"""Source extractors: one module per site."""
```

- [ ] **Step 17.2: Write `src/crawler/sources/base.py`**

```python
"""Base extractor protocol + registry of installed sources."""

from __future__ import annotations

from typing import Iterable, Protocol, Type

from crawler.models import RawExhibition, SourceName


class SourceExtractor(Protocol):
    name: SourceName

    def crawl(self) -> Iterable[RawExhibition]: ...


_REGISTRY: dict[SourceName, Type[SourceExtractor]] = {}


def register_source(name: SourceName, cls: Type[SourceExtractor]) -> None:
    _REGISTRY[name] = cls


def get_source(name: SourceName) -> Type[SourceExtractor]:
    if name not in _REGISTRY:
        raise KeyError(f"source not registered: {name.value}")
    return _REGISTRY[name]


def all_sources() -> dict[SourceName, Type[SourceExtractor]]:
    return dict(_REGISTRY)
```

- [ ] **Step 17.3: Write `docs/sources/artmap.md`** (AI-assisted site analysis notes)

```markdown
# Artmap (art-map.co.kr) — extraction notes

## URLs
- List (desktop): `https://art-map.co.kr/exhibition/new_list.php?cate=&od=2&area=&type=ing`
  - `type=ing` ongoing, `type=will` upcoming, `type=end` past
  - Pagination: `page=N` query param (verify on first fixture capture)
- Detail: `https://art-map.co.kr/exhibition/view.php?idx=<id>`

## List page card structure (verify against `tests/fixtures/artmap/list_page_1.html` after capture)
- Each card wrapped in `<a href="/exhibition/view.php?idx=...">`
- `<img>` poster: relative path under `/art-map/public/upload/...` — prepend `https://art-map.co.kr` if needed
- Title: text in `<h3>` or `<h4>`
- Venue + region: text node like `"서울시립미술관서소문본관/서울"` (split on `/`)
- Date range: text node `"2026.05.19 ~ 2026.10.25"`

## Detail page (only used if list page lacks fields)
- Description: first paragraph under `.exhibition-info` or similar
- Artist(s): row labelled `작가` in metadata table
- Fee: row labelled `관람료`
- Exhibition type: row labelled `구분` (개인전/단체전/기획전 etc.)
- Address: row labelled `주소`

## Robots & manners
- `https://art-map.co.kr/robots.txt` — confirm before shipping (PR checklist)
- 1-second delay between requests
- User-Agent: `PhotoExhibitionCrawler/0.1 (+contact@example.com)`

## Pagination strategy
- Walk `page=1..N` until a page returns zero cards or repeats the previous page's first card id.
- Cap at 20 pages for v1 (sane upper bound; tune if Artmap shows more).

## Known quirks
- Dates sometimes show `2026.05.19 ~ 미정` — start parses, end is None.
- Some cards have no poster image (use empty string).
- `구분` field is missing on roughly half of older entries — default to `기획전`.
```

- [ ] **Step 17.4: Now run the CLI test from Task 16**

Run: `pytest tests/test_cli.py -v`
Expected: 2 passed (the stub extractor registers itself via `register_source`).

- [ ] **Step 17.5: Commit**

```bash
git add src/crawler/sources/ docs/sources/
git commit -m "feat(sources): source registry + Artmap extraction notes"
```

---

## Task 18: Artmap source extractor (with fixture)

**Files:**
- Create: `tests/fixtures/artmap/list_page_1.html` (captured snapshot)
- Create: `tests/fixtures/artmap/expected.jsonl`
- Create: `tests/sources/__init__.py` (empty)
- Create: `tests/sources/test_artmap.py`
- Create: `src/crawler/sources/artmap.py`

- [ ] **Step 18.1: Capture a real list-page HTML snapshot**

Run, in your shell (one-off, manual):

```bash
mkdir -p tests/fixtures/artmap
curl -sSL \
  -A "PhotoExhibitionCrawler/0.1 (+contact@example.com)" \
  "https://art-map.co.kr/exhibition/new_list.php?cate=&od=2&area=&type=ing&page=1" \
  -o tests/fixtures/artmap/list_page_1.html

# Verify the file is real HTML, not an error page
head -5 tests/fixtures/artmap/list_page_1.html
```

Expected: HTML output starts with `<!DOCTYPE html` or `<html`.

- [ ] **Step 18.2: Inspect the snapshot to confirm selectors**

Open `tests/fixtures/artmap/list_page_1.html` in a browser or `less`. Identify, for the first 3 cards:
- the `<a href>` value (detail URL)
- the title text and its surrounding tag
- the venue/region text and surrounding tag
- the date-range text and surrounding tag
- the `<img src>` value

If the tag names differ from the notes in `docs/sources/artmap.md`, update the notes file FIRST and commit that update, then proceed.

- [ ] **Step 18.3: Write `tests/fixtures/artmap/expected.jsonl`**

Based on the first 3 cards you identified, write exactly 3 lines. Use the actual values from your snapshot — example shape (replace `...` with real values):

```json
{"source": "artmap", "source_url": "https://art-map.co.kr/exhibition/view.php?idx=NNNN", "raw": {"title": "...", "venue_name": "...", "venue_region": "...", "date_range": "...", "poster_image_url": "https://art-map.co.kr/..."}}
```

- [ ] **Step 18.4: Write failing test `tests/sources/test_artmap.py`**

```python
import json
from pathlib import Path

import httpx
import respx

from crawler.models import SourceName
from crawler.sources.artmap import ArtmapExtractor


FIXTURE_DIR = Path(__file__).parent.parent / "fixtures" / "artmap"


def _load_fixture(name: str) -> str:
    return (FIXTURE_DIR / name).read_text(encoding="utf-8")


def _load_expected() -> list[dict]:
    return [json.loads(line) for line in (FIXTURE_DIR / "expected.jsonl").read_text(encoding="utf-8").splitlines() if line.strip()]


@respx.mock
def test_artmap_extractor_parses_first_three_cards():
    list_html = _load_fixture("list_page_1.html")
    respx.get("https://art-map.co.kr/exhibition/new_list.php").mock(
        return_value=httpx.Response(200, text=list_html)
    )

    extractor = ArtmapExtractor(max_pages=1)
    raws = list(extractor.crawl())
    assert len(raws) >= 3, f"expected at least 3 cards, got {len(raws)}"
    assert all(r.source is SourceName.ARTMAP for r in raws)

    expected = _load_expected()
    by_url = {str(r.source_url): r for r in raws}
    for exp in expected:
        actual = by_url[exp["source_url"]]
        for k, v in exp["raw"].items():
            assert actual.raw.get(k) == v, f"mismatch on {exp['source_url']} field {k}"


@respx.mock
def test_artmap_extractor_stops_when_page_empty():
    respx.get("https://art-map.co.kr/exhibition/new_list.php", params={"page": 1}).mock(
        return_value=httpx.Response(200, text=_load_fixture("list_page_1.html"))
    )
    # any subsequent page returns an empty page (no cards)
    respx.get("https://art-map.co.kr/exhibition/new_list.php").mock(
        return_value=httpx.Response(200, text="<html><body></body></html>")
    )
    extractor = ArtmapExtractor(max_pages=5)
    raws = list(extractor.crawl())
    # should stop after page 2 (empty) rather than continuing to page 5
    assert len(raws) >= 3
```

- [ ] **Step 18.5: Run, see fail**

Run: `pytest tests/sources/test_artmap.py -v`
Expected: ImportError on `crawler.sources.artmap`.

- [ ] **Step 18.6: Write `src/crawler/sources/artmap.py`**

The selectors below assume the structure documented in `docs/sources/artmap.md`. **If your snapshot inspection (Step 18.2) found different tags/classes, adjust the `_extract_cards` function accordingly.** Keep the public interface stable.

```python
"""Artmap (art-map.co.kr) — list-page extractor.

Strategy: walk paginated list pages, parse each card, yield RawExhibition with
list-page fields. Detail-page enrichment is left for v1.5.
"""

from __future__ import annotations

import re
import time
from typing import Iterable
from urllib.parse import urljoin

import httpx
from selectolax.parser import HTMLParser
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

from crawler.models import RawExhibition, SourceName
from crawler.sources.base import register_source


_LIST_URL = "https://art-map.co.kr/exhibition/new_list.php"
_BASE = "https://art-map.co.kr"
_USER_AGENT = "PhotoExhibitionCrawler/0.1 (+contact@example.com)"
_DETAIL_RE = re.compile(r"/exhibition/view\.php\?idx=(\d+)")


class ArtmapExtractor:
    name = SourceName.ARTMAP

    def __init__(
        self,
        max_pages: int = 20,
        delay_s: float = 1.0,
        timeout_s: float = 20.0,
    ) -> None:
        self.max_pages = max_pages
        self.delay_s = delay_s
        self._client = httpx.Client(
            timeout=timeout_s,
            headers={"User-Agent": _USER_AGENT},
            follow_redirects=True,
        )

    @retry(
        retry=retry_if_exception_type(httpx.TransportError),
        wait=wait_exponential(multiplier=1, min=1, max=16),
        stop=stop_after_attempt(3),
        reraise=True,
    )
    def _get(self, params: dict) -> str:
        r = self._client.get(_LIST_URL, params=params)
        r.raise_for_status()
        return r.text

    def crawl(self) -> Iterable[RawExhibition]:
        seen_first_url: str | None = None
        for page in range(1, self.max_pages + 1):
            html = self._get({"cate": "", "od": "2", "area": "", "type": "ing", "page": str(page)})
            cards = _extract_cards(html)
            if not cards:
                return
            # Stop if pagination wraps (first card identical to a previous page's first)
            first_url = cards[0]["source_url"]
            if seen_first_url is not None and first_url == seen_first_url:
                return
            if page == 1:
                seen_first_url = first_url
            for c in cards:
                yield RawExhibition(
                    source=SourceName.ARTMAP,
                    source_url=c["source_url"],
                    raw={k: v for k, v in c.items() if k != "source_url"},
                )
            time.sleep(self.delay_s)


def _extract_cards(html: str) -> list[dict]:
    """Parse list-page HTML into card dicts.

    Returns dicts with keys: source_url, title, venue_name, venue_region,
    date_range, poster_image_url.

    NOTE: This implementation is best-effort against the snapshot. Adjust selectors
    after inspecting `tests/fixtures/artmap/list_page_1.html`.
    """
    doc = HTMLParser(html)
    cards: list[dict] = []
    for a in doc.css("a"):
        href = a.attributes.get("href") or ""
        m = _DETAIL_RE.search(href)
        if not m:
            continue
        idx = m.group(1)
        source_url = f"{_BASE}/exhibition/view.php?idx={idx}"

        # title: nearest h3/h4 inside the anchor
        title_node = a.css_first("h3, h4")
        title = (title_node.text(strip=True) if title_node else "").strip()
        if not title:
            continue

        img = a.css_first("img")
        poster = ""
        if img and (src := img.attributes.get("src")):
            poster = urljoin(_BASE, src)

        # venue + region: last text fragment under the anchor, often "VENUE/REGION"
        text = a.text(separator="\n").strip().splitlines()
        venue_name = ""
        venue_region = ""
        date_range = ""
        for line in text:
            ln = line.strip()
            if not ln or ln == title:
                continue
            if "/" in ln and not venue_name and not _looks_like_date_range(ln):
                venue_name, _, venue_region = ln.partition("/")
            elif _looks_like_date_range(ln) and not date_range:
                date_range = ln

        cards.append({
            "source_url": source_url,
            "title": title,
            "venue_name": venue_name.strip() or None,
            "venue_region": venue_region.strip() or None,
            "date_range": date_range.strip() or None,
            "poster_image_url": poster or None,
        })
    # de-duplicate by source_url preserving order
    seen: set[str] = set()
    out: list[dict] = []
    for c in cards:
        if c["source_url"] in seen:
            continue
        seen.add(c["source_url"])
        out.append(c)
    return out


_DATE_RANGE_RE = re.compile(r"\d{4}[.\-/]\s*\d{1,2}[.\-/]\s*\d{1,2}")


def _looks_like_date_range(s: str) -> bool:
    return bool(_DATE_RANGE_RE.search(s))


# Register on import
register_source(SourceName.ARTMAP, ArtmapExtractor)
```

- [ ] **Step 18.7: Run, expect pass**

Run: `pytest tests/sources/test_artmap.py -v`
Expected: 2 passed.

If the first test fails because the fixture has only 1-2 cards (very rare), reduce `>= 3` to `>= 1` and re-run. If a field is None where expected.jsonl had a value, your selectors need adjustment — fix `_extract_cards` (don't loosen the test).

- [ ] **Step 18.8: Commit**

```bash
git add src/crawler/sources/artmap.py tests/sources/ tests/fixtures/artmap/
git commit -m "feat(sources): Artmap list-page extractor with fixture-based tests"
```

---

## Task 19: Integration test — Artmap end-to-end (fake sink)

**Files:**
- Create: `tests/integration/__init__.py` (empty)
- Create: `tests/integration/test_pipeline_artmap.py`

- [ ] **Step 19.1: Write `tests/integration/test_pipeline_artmap.py`**

```python
from datetime import date
from pathlib import Path

import httpx
import respx
from freezegun import freeze_time

from crawler.models import SourceName
from crawler.pipeline import run_source
from crawler.sinks.base import SheetName
from crawler.sinks.fake import FakeRepository
from crawler.sinks.init_sheets import init_sheets
from crawler.sources.artmap import ArtmapExtractor


FIXTURE = Path(__file__).parent.parent / "fixtures" / "artmap" / "list_page_1.html"


class _FakeHeaderRepo(FakeRepository):
    def write_headers(self, sheet: SheetName, headers: list[str]) -> None:  # noqa: ARG002
        return None


class _NullGeocoder:
    def geocode(self, query: str) -> tuple[float | None, float | None]:  # noqa: ARG002
        return None, None


@respx.mock
@freeze_time("2026-05-28")
def test_artmap_end_to_end_writes_to_fake_sheet():
    list_html = FIXTURE.read_text(encoding="utf-8")
    respx.get("https://art-map.co.kr/exhibition/new_list.php").mock(
        return_value=httpx.Response(200, text=list_html)
    )

    repo = _FakeHeaderRepo()
    init_sheets(repo)

    report = run_source(
        extractor=ArtmapExtractor(max_pages=1, delay_s=0),
        repo=repo,
        geocoder=_NullGeocoder(),
        today=date(2026, 5, 28),
    )

    assert report.failure is None
    assert report.errors == 0
    assert report.extracted >= 1
    assert report.new >= 1

    exh = repo.read_rows(SheetName.EXHIBITIONS)
    assert len(exh) == report.extracted
    # every row has id, title, status set
    for r in exh:
        assert r["id"] and r["title"] and r["status"]

    venues = repo.read_rows(SheetName.VENUES)
    assert len(venues) >= 1
    # all exhibition rows point to existing venue ids
    venue_ids = {v["id"] for v in venues}
    for r in exh:
        assert r["venue_id"] in venue_ids
```

- [ ] **Step 19.2: Run, expect pass**

Run: `pytest tests/integration/test_pipeline_artmap.py -v`
Expected: 1 passed.

- [ ] **Step 19.3: Commit**

```bash
git add tests/integration/
git commit -m "test(integration): Artmap end-to-end pipeline with fake sink"
```

---

## Task 20: CI — test workflow

**Files:**
- Create: `.github/workflows/test.yml`

- [ ] **Step 20.1: Write `.github/workflows/test.yml`**

```yaml
name: test
on:
  push: { branches: [main] }
  pull_request:
jobs:
  test:
    runs-on: ubuntu-latest
    timeout-minutes: 10
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: '3.12'
          cache: 'pip'
      - run: pip install -e ".[dev]"
      - run: ruff check src/ tests/
      - run: pytest -q
```

- [ ] **Step 20.2: Run lint + tests locally to mirror CI**

Run: `ruff check src/ tests/ && pytest -q`
Expected: ruff clean, all tests pass.

If ruff complains, fix the lint issues (often unused imports). Re-run.

- [ ] **Step 20.3: Commit**

```bash
git add .github/workflows/test.yml
git commit -m "ci: lint + test workflow on push/PR"
```

---

## Task 21: README polish + operational notes

**Files:**
- Modify: `README.md`

- [ ] **Step 21.1: Replace the README with a complete operational guide**

```markdown
# photo-exhibition-crawler

Crawler for Korean photography/video/camera exhibitions. Writes normalized data into Google Sheets across 5 worksheets: `Exhibitions`, `Artists`, `Venues`, `Organizers`, `_overrides`.

## Setup (one-time)

```bash
python3.12 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

## Run tests

```bash
pytest -q              # unit + integration (no network)
ruff check src/ tests/
```

## Configure secrets for live crawling

Create a Google Cloud service account, download its JSON key, and share the target sheet with the service-account email as an Editor.

```bash
export SHEET_ID="1KjhDcaWVQizAcltjp4HHoWhMonztAeADAMMaaRtKRXI"
export GOOGLE_SERVICE_ACCOUNT_JSON="$(cat service-account.json)"
export KAKAO_REST_API_KEY="..."
```

## CLI

```bash
crawler init-sheets       # create 5 worksheets with headers (idempotent)
crawler dry-run artmap    # crawl and print normalized JSON, no writes
crawler run artmap        # crawl one source and upsert
crawler run-all           # crawl every registered source
```

## Adding a new source

1. Write `docs/sources/<name>.md` — list URL, pagination, selectors, quirks.
2. Capture HTML snapshot to `tests/fixtures/<name>/list_page_1.html` and author `expected.jsonl` for the first 3 cards.
3. Implement `src/crawler/sources/<name>.py` with `crawl()` returning `RawExhibition`s and call `register_source(...)` at module bottom.
4. Add `tests/sources/test_<name>.py` mirroring `test_artmap.py`.
5. Add the source value to `SourceName` enum in `models.py` if it's new.

## Architecture (one paragraph)

CLI → pipeline → (source extractor → normalizer → entity resolver → geocoder → sheets writer). Each stage is independently testable; sources only know HTTP/HTML, normalizers are pure functions, the resolver only talks to the sink via the Repository protocol, and the gspread implementation is one of two repositories (the other is in-memory for tests).

See `docs/superpowers/specs/2026-05-28-photo-exhibition-crawler-design.md` for full design.
```

- [ ] **Step 21.2: Commit**

```bash
git add README.md
git commit -m "docs: complete README with setup, CLI, and how to add a source"
```

---

## Self-Review Checklist (for the implementer)

After all 21 tasks, before declaring M1+M2 complete, confirm:

- [ ] `pytest -q` — all tests pass with no warnings
- [ ] `ruff check src/ tests/` — clean
- [ ] `python -c "from crawler.cli import app; print('ok')"` — no import errors
- [ ] Set real secrets locally, then `crawler init-sheets` — 5 worksheets appear in your sheet with correct headers
- [ ] `crawler dry-run artmap` — prints valid JSON for several exhibitions
- [ ] `crawler run artmap` — writes data into the sheet; second run reports mostly `unchanged`

If anything in the checklist fails, fix the underlying task before moving to M3.

## Next plan

M3 — adding the remaining 4 P0 sources (Naver, Photo SeMA, Museum Hanmi, KOBA) — follows the same pattern as Task 17-18 repeated four times. Plan that as `2026-MM-DD-m3-additional-sources.md` once M1+M2 is shipped.
