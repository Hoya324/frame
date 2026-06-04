# 거장의 시선 (Master's Gaze) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a curated "거장의 시선" section — public-domain photography masters and their works with Gemini-written commentary — exposed as `/masters` pages plus a 1.4s auto-advancing home hero carousel that mixes random featured exhibitions and master slides.

**Architecture:** An independent Python pipeline under `src/crawler/masters/` pulls public-domain works from free, keyless museum APIs (The Met, Art Institute of Chicago), selects representative works, has Gemini write ko bio/commentary (then reuses the existing translator for en/ja), and writes `web/public/data/masters.json`. The Next.js app reads that file via a `masters.ts` lib mirroring `catalog.ts`, renders `/masters` list + detail pages, and replaces the single home hero with a `FeaturedCarousel`. The existing exhibitions pipeline is untouched.

**Tech Stack:** Python 3.12 (httpx, tenacity, pydantic, Typer, respx + pytest for tests), Next.js/React (TypeScript, vitest), Gemini via the existing `GeminiTranslator`.

---

## Conventions every task follows

- **TDD:** write the failing test, run it red, implement minimally, run it green, commit. One logical change per commit.
- Python CI gate: `ruff check src/ tests/` + `pytest -q` must pass before each commit. mypy is **not** in CI — follow existing `register_source`/pydantic patterns; don't chase mypy.
- Web CI gate (run inside `web/`): `npm run lint` + `npx vitest run` must pass before committing web changes.
- HTTP tests mock with `respx` (see `tests/sources/test_pgi.py` for the pattern). Gemini is always **mocked** in tests — never call the live API from a test.
- Commit message convention: Conventional Commits (`feat(masters): …`, `test(masters): …`, etc.).
- The shared desktop UA string (copied from `pgi.py`):
  `Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Safari/537.36`

---

## File structure

**Python pipeline — `src/crawler/masters/` (new package):**
- `__init__.py` — empty package marker.
- `models.py` — `RawWork` (one candidate work from a museum) + `MasterSeed`/`SourceQuery` (roster entry).
- `museums/__init__.py`, `museums/base.py` — `MuseumClient` protocol.
- `museums/the_met.py` — The Met Collection API client.
- `museums/aic.py` — Art Institute of Chicago API client.
- `roster.py` — `ROSTER: list[MasterSeed]`, the curated seed list.
- `select.py` — `select_works(seed, clients, cap)` → filtered/ranked/capped `list[RawWork]`.
- `cache.py` — `CommentaryCache` JSON file cache (id + facts-hash → {ko,en,ja}).
- `commentary.py` — `CommentaryWriter` (Gemini-generate ko, translate to en/ja).
- `build.py` — `build_masters(...)` orchestration → masters.json dict + `write_masters(...)`.

**Python shared:**
- `src/crawler/enrich/translator.py` — add a generic `GeminiTranslator.generate(prompt)`.
- `src/crawler/cli.py` — add `build-masters` command.

**CI:**
- `.github/workflows/build-masters.yml` — `workflow_dispatch` + monthly cron.

**Web — `web/src/`:**
- `lib/masters.ts` — types + `parseMasters` + `loadMasters` (mirrors `catalog.ts`).
- `lib/carousel.ts` — `buildCarouselSlides(exhibitions, masters, rng)` pure builder.
- `lib/i18n.ts` — add `masters.*` keys (modify).
- `components/FeaturedCarousel.tsx` — the auto-advancing hero carousel.
- `app/page.tsx` — replace the single hero with `<FeaturedCarousel>` (modify).
- `app/masters/page.tsx` — list grouped by region.
- `app/masters/[id]/page.tsx` — master detail + works gallery.
- `public/data/masters.json` — generated data file (committed).

**Tests:**
- `tests/masters/` — `test_the_met.py`, `test_aic.py`, `test_select.py`, `test_cache.py`, `test_commentary.py`, `test_build.py`.
- `tests/fixtures/masters/` — captured API JSON.
- `web/src/lib/masters.test.ts`, `web/src/lib/carousel.test.ts`, `web/src/components/FeaturedCarousel.test.tsx`.

---

## Task 1: Pipeline models (`RawWork`, `MasterSeed`, `SourceQuery`)

**Files:**
- Create: `src/crawler/masters/__init__.py` (empty)
- Create: `src/crawler/masters/models.py`
- Test: `tests/masters/__init__.py` (empty), `tests/masters/test_models.py`

- [ ] **Step 1: Write the failing test**

Create `tests/masters/__init__.py` (empty) and `tests/masters/test_models.py`:

```python
from crawler.masters.models import MasterSeed, RawWork, SourceQuery


def test_rawwork_has_image_true_when_image_url_present():
    w = RawWork(
        source="the_met", source_object_id="269725", title="Le Pont Neuf",
        year="1900", medium="Albumen silver print", image_url="https://x/full.jpg",
        thumb_url="https://x/small.jpg", source_url="https://x/269725",
        credit="The Met · CC0", is_public_domain=True, is_highlight=True,
    )
    assert w.has_image is True
    assert w.work_id == "the_met-269725"


def test_rawwork_has_image_false_when_no_image():
    w = RawWork(
        source="aic", source_object_id="1", title="x", year=None, medium=None,
        image_url=None, thumb_url=None, source_url="https://x/1", credit="AIC",
        is_public_domain=True, is_highlight=False,
    )
    assert w.has_image is False


def test_masterseed_explicit_ids_and_query_sources():
    seed = MasterSeed(
        id="eugene-atget", name="Eugène Atget", region="foreign", nationality="FR",
        birth_year=1857, death_year=1927, portrait_url="https://x/atget.jpg",
        sources=[
            SourceQuery(source="the_met", object_ids=["269725", "283181"]),
            SourceQuery(source="aic", query="Eugène Atget"),
        ],
    )
    assert seed.sources[0].object_ids == ["269725", "283181"]
    assert seed.sources[0].query is None
    assert seed.sources[1].query == "Eugène Atget"
    assert seed.region == "foreign"
```

- [ ] **Step 2: Run it red**

Run: `pytest tests/masters/test_models.py -q`
Expected: FAIL (`ModuleNotFoundError: crawler.masters`).

- [ ] **Step 3: Implement**

Create `src/crawler/masters/__init__.py` (empty file).

Create `src/crawler/masters/models.py`:

```python
"""Data shapes for the masters pipeline: a candidate work from a museum API,
and a curated roster seed describing where to pull a master's works from."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class RawWork:
    """One candidate work returned by a museum client, pre-selection."""

    source: str  # museum source key, e.g. "the_met"
    source_object_id: str  # the museum's own object id
    title: str
    year: str | None
    medium: str | None
    image_url: str | None  # full/large hosted image (CC0)
    thumb_url: str | None  # smaller variant for grids/carousels
    source_url: str  # museum object page
    credit: str  # attribution / license line
    is_public_domain: bool
    is_highlight: bool = False

    @property
    def has_image(self) -> bool:
        return bool(self.image_url)

    @property
    def work_id(self) -> str:
        return f"{self.source}-{self.source_object_id}"


@dataclass(frozen=True)
class SourceQuery:
    """Where to pull one master's works from a single museum. Provide
    ``object_ids`` to hand-pick exact iconic works (preferred), OR ``query`` to
    auto-pull by artist search. Exactly one of the two should be set."""

    source: str
    query: str | None = None
    object_ids: list[str] | None = None


@dataclass(frozen=True)
class MasterSeed:
    """A curated master and the museum sources for their works."""

    id: str  # stable kebab-case slug
    name: str  # original-language display name
    region: str  # "kr" | "jp" | "foreign"
    nationality: str  # ISO 3166-1 alpha-2
    birth_year: int | None
    death_year: int | None
    portrait_url: str | None  # PD portrait (Wikimedia), curated here
    sources: list[SourceQuery] = field(default_factory=list)
```

- [ ] **Step 4: Run it green**

Run: `pytest tests/masters/test_models.py -q` → PASS.

- [ ] **Step 5: Commit**

```bash
git add src/crawler/masters/__init__.py src/crawler/masters/models.py tests/masters/
git commit -m "feat(masters): RawWork + MasterSeed pipeline models"
```

---

## Task 2: The Met museum client

The Met Collection API is free and keyless. Endpoints:
- Search: `GET https://collectionapi.metmuseum.org/public/collection/v1/search?q={name}&artistOrCulture=true&medium=Photographs` → `{"total": N, "objectIDs": [int,...] | null}`.
- Object: `GET .../public/collection/v1/objects/{id}` → fields used: `objectID`, `isPublicDomain` (bool), `primaryImage`, `primaryImageSmall`, `title`, `objectDate`, `medium`, `objectURL`, `creditLine`, `isHighlight`.

**Files:**
- Create: `src/crawler/masters/museums/__init__.py` (empty), `src/crawler/masters/museums/base.py`, `src/crawler/masters/museums/the_met.py`
- Create: `tests/fixtures/masters/met_object_269725.json`, `tests/fixtures/masters/met_search_atget.json`
- Test: `tests/masters/test_the_met.py`

- [ ] **Step 1: Capture fixtures**

```bash
mkdir -p tests/fixtures/masters
curl -sL 'https://collectionapi.metmuseum.org/public/collection/v1/search?q=Eug%C3%A8ne%20Atget&artistOrCulture=true&medium=Photographs' -o tests/fixtures/masters/met_search_atget.json
# pick a public-domain object id from the search result's objectIDs, then:
curl -sL 'https://collectionapi.metmuseum.org/public/collection/v1/objects/269725' -o tests/fixtures/masters/met_object_269725.json
```
Open `met_object_269725.json`; confirm `isPublicDomain` and `primaryImage` are present. If 269725 is not public-domain in the live data, pick an id whose object JSON has `"isPublicDomain": true` and a non-empty `primaryImage`, save it under that id, and use that id in the test below.

- [ ] **Step 2: Write the failing test**

Create `src/crawler/masters/museums/__init__.py` (empty). Create `tests/masters/test_the_met.py`:

```python
import json
from pathlib import Path

import httpx
import respx

from crawler.masters.museums.the_met import MetClient

FIX = Path(__file__).parent.parent / "fixtures" / "masters"


def _obj():
    return json.loads((FIX / "met_object_269725.json").read_text())


def _search():
    return json.loads((FIX / "met_search_atget.json").read_text())


@respx.mock
def test_fetch_by_ids_maps_public_domain_object():
    respx.get(
        "https://collectionapi.metmuseum.org/public/collection/v1/objects/269725"
    ).mock(return_value=httpx.Response(200, json=_obj()))

    client = MetClient()
    works = client.fetch_by_ids(["269725"])

    assert len(works) == 1
    w = works[0]
    assert w.source == "the_met"
    assert w.source_object_id == "269725"
    assert w.is_public_domain is True
    assert w.image_url  # primaryImage
    assert w.source_url.startswith("https://www.metmuseum.org/")
    assert w.work_id == "the_met-269725"


@respx.mock
def test_search_works_pulls_objects_for_query():
    search_json = {"total": 1, "objectIDs": [269725]}
    respx.get(
        "https://collectionapi.metmuseum.org/public/collection/v1/search"
    ).mock(return_value=httpx.Response(200, json=search_json))
    respx.get(
        "https://collectionapi.metmuseum.org/public/collection/v1/objects/269725"
    ).mock(return_value=httpx.Response(200, json=_obj()))

    works = MetClient().search_works("Eugène Atget", limit=5)
    assert [w.source_object_id for w in works] == ["269725"]


@respx.mock
def test_search_handles_null_objectids():
    respx.get(
        "https://collectionapi.metmuseum.org/public/collection/v1/search"
    ).mock(return_value=httpx.Response(200, json={"total": 0, "objectIDs": None}))
    assert MetClient().search_works("Nobody", limit=5) == []
```

- [ ] **Step 3: Run it red**

Run: `pytest tests/masters/test_the_met.py -q` → FAIL (no module `the_met`).

- [ ] **Step 4: Implement the protocol + client**

Create `src/crawler/masters/museums/base.py`:

```python
"""Common interface every museum client implements."""

from __future__ import annotations

from typing import Protocol

from crawler.masters.models import RawWork


class MuseumClient(Protocol):
    source: str

    def fetch_by_ids(self, object_ids: list[str]) -> list[RawWork]:
        """Fetch specific objects by their museum ids, preserving order."""
        ...

    def search_works(self, query: str, limit: int) -> list[RawWork]:
        """Search by artist/name and return up to ``limit`` candidate works."""
        ...
```

Create `src/crawler/masters/museums/the_met.py`:

```python
"""The Metropolitan Museum of Art Open Access (CC0) client. Free, no API key."""

from __future__ import annotations

import logging

import httpx
from tenacity import retry, stop_after_attempt, wait_exponential

from crawler.masters.models import RawWork

logger = logging.getLogger(__name__)

_BASE = "https://collectionapi.metmuseum.org/public/collection/v1"


class MetClient:
    source = "the_met"

    def __init__(self, client: httpx.Client | None = None) -> None:
        self._client = client or httpx.Client(timeout=30.0)

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(max=10), reraise=True)
    def _get(self, url: str, params: dict | None = None) -> dict:
        r = self._client.get(url, params=params)
        r.raise_for_status()
        return r.json()

    def _object(self, object_id: str) -> RawWork | None:
        try:
            data = self._get(f"{_BASE}/objects/{object_id}")
        except httpx.HTTPStatusError:
            logger.warning("the_met: object %s fetch failed", object_id)
            return None
        return _to_work(data)

    def fetch_by_ids(self, object_ids: list[str]) -> list[RawWork]:
        out: list[RawWork] = []
        for oid in object_ids:
            w = self._object(oid)
            if w is not None:
                out.append(w)
        return out

    def search_works(self, query: str, limit: int) -> list[RawWork]:
        data = self._get(
            f"{_BASE}/search",
            params={"q": query, "artistOrCulture": "true", "medium": "Photographs"},
        )
        ids = data.get("objectIDs") or []
        works: list[RawWork] = []
        # Search returns many ids ranked by relevance; walk until we have `limit`
        # public-domain, image-bearing works (cap the walk so a bad query can't
        # fan out into hundreds of object requests).
        for oid in ids[: max(limit * 4, limit)]:
            w = self._object(str(oid))
            if w is not None and w.is_public_domain and w.has_image:
                works.append(w)
            if len(works) >= limit:
                break
        return works


def _to_work(data: dict) -> RawWork:
    return RawWork(
        source="the_met",
        source_object_id=str(data.get("objectID", "")),
        title=data.get("title") or "Untitled",
        year=(data.get("objectDate") or None),
        medium=(data.get("medium") or None),
        image_url=(data.get("primaryImage") or None),
        thumb_url=(data.get("primaryImageSmall") or data.get("primaryImage") or None),
        source_url=data.get("objectURL") or "",
        credit=data.get("creditLine") or "The Metropolitan Museum of Art",
        is_public_domain=bool(data.get("isPublicDomain")),
        is_highlight=bool(data.get("isHighlight")),
    )
```

- [ ] **Step 5: Run it green**

Run: `pytest tests/masters/test_the_met.py -q` → PASS. If a field assertion fails, reconcile the test's expected values against the actual captured fixture (the fixture is ground truth).

- [ ] **Step 6: Commit**

```bash
git add src/crawler/masters/museums/ tests/masters/test_the_met.py tests/fixtures/masters/met_*.json
git commit -m "feat(masters): The Met open-access client"
```

---

## Task 3: Art Institute of Chicago client

AIC API is free and keyless (politeness UA recommended). Endpoints:
- Search: `GET https://api.artic.edu/api/v1/artworks/search?q={name}&fields=id,title,date_display,medium_display,image_id,is_public_domain&limit={n}` → `{"data": [ {id,title,date_display,medium_display,image_id,is_public_domain}, ... ]}`.
- Object: `GET https://api.artic.edu/api/v1/artworks/{id}?fields=...` → `{"data": {...}}`.
- IIIF image: `https://www.artic.edu/iiif/2/{image_id}/full/843,/0/default.jpg` (full) and `.../full/200,/0/default.jpg` (thumb). Object page: `https://www.artic.edu/artworks/{id}`.

**Files:**
- Create: `src/crawler/masters/museums/aic.py`
- Create: `tests/fixtures/masters/aic_search_stieglitz.json`, `tests/fixtures/masters/aic_object.json`
- Test: `tests/masters/test_aic.py`

- [ ] **Step 1: Capture fixtures**

```bash
curl -sL -A 'frame-photo (hoyana1225@gmail.com)' 'https://api.artic.edu/api/v1/artworks/search?q=Alfred%20Stieglitz&fields=id,title,date_display,medium_display,image_id,is_public_domain&limit=10' -o tests/fixtures/masters/aic_search_stieglitz.json
# pick an id from data[] that has is_public_domain=true and a non-null image_id, then:
curl -sL -A 'frame-photo (hoyana1225@gmail.com)' 'https://api.artic.edu/api/v1/artworks/<ID>?fields=id,title,date_display,medium_display,image_id,is_public_domain' -o tests/fixtures/masters/aic_object.json
```
Note the id you saved; use it in the test below.

- [ ] **Step 2: Write the failing test**

Create `tests/masters/test_aic.py`:

```python
import json
from pathlib import Path

import httpx
import respx

from crawler.masters.museums.aic import AicClient

FIX = Path(__file__).parent.parent / "fixtures" / "masters"


def _search():
    return json.loads((FIX / "aic_search_stieglitz.json").read_text())


def _object():
    return json.loads((FIX / "aic_object.json").read_text())


@respx.mock
def test_search_builds_iiif_urls_and_filters_to_pd_with_image():
    data = {
        "data": [
            {"id": 100, "title": "The Steerage", "date_display": "1907",
             "medium_display": "Photogravure", "image_id": "abc", "is_public_domain": True},
            {"id": 101, "title": "No Image", "date_display": "1910",
             "medium_display": "Print", "image_id": None, "is_public_domain": True},
            {"id": 102, "title": "In Copyright", "date_display": "1950",
             "medium_display": "Print", "image_id": "def", "is_public_domain": False},
        ]
    }
    respx.get("https://api.artic.edu/api/v1/artworks/search").mock(
        return_value=httpx.Response(200, json=data)
    )

    works = AicClient().search_works("Alfred Stieglitz", limit=10)

    assert [w.source_object_id for w in works] == ["100"]  # only PD + has image
    w = works[0]
    assert w.source == "aic"
    assert w.image_url == "https://www.artic.edu/iiif/2/abc/full/843,/0/default.jpg"
    assert w.thumb_url == "https://www.artic.edu/iiif/2/abc/full/200,/0/default.jpg"
    assert w.source_url == "https://www.artic.edu/artworks/100"
    assert w.year == "1907"


@respx.mock
def test_fetch_by_ids_maps_object():
    obj = {"data": {"id": 100, "title": "The Steerage", "date_display": "1907",
                    "medium_display": "Photogravure", "image_id": "abc",
                    "is_public_domain": True}}
    respx.get("https://api.artic.edu/api/v1/artworks/100").mock(
        return_value=httpx.Response(200, json=obj)
    )
    works = AicClient().fetch_by_ids(["100"])
    assert works[0].work_id == "aic-100"
    assert works[0].is_public_domain is True
```

- [ ] **Step 3: Run it red**

Run: `pytest tests/masters/test_aic.py -q` → FAIL.

- [ ] **Step 4: Implement**

Create `src/crawler/masters/museums/aic.py`:

```python
"""Art Institute of Chicago Open Access (CC0) client. Free, no API key.
A descriptive User-Agent is requested by AIC's API guidelines."""

from __future__ import annotations

import logging

import httpx
from tenacity import retry, stop_after_attempt, wait_exponential

from crawler.masters.models import RawWork

logger = logging.getLogger(__name__)

_BASE = "https://api.artic.edu/api/v1/artworks"
_IIIF = "https://www.artic.edu/iiif/2"
_FIELDS = "id,title,date_display,medium_display,image_id,is_public_domain"
_UA = "frame-photo (hoyana1225@gmail.com)"


class AicClient:
    source = "aic"

    def __init__(self, client: httpx.Client | None = None) -> None:
        self._client = client or httpx.Client(timeout=30.0, headers={"AIC-User-Agent": _UA})

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(max=10), reraise=True)
    def _get(self, url: str, params: dict | None = None) -> dict:
        r = self._client.get(url, params=params)
        r.raise_for_status()
        return r.json()

    def search_works(self, query: str, limit: int) -> list[RawWork]:
        data = self._get(f"{_BASE}/search", params={"q": query, "fields": _FIELDS, "limit": limit})
        out: list[RawWork] = []
        for rec in data.get("data") or []:
            w = _to_work(rec)
            if w is not None and w.is_public_domain and w.has_image:
                out.append(w)
        return out

    def fetch_by_ids(self, object_ids: list[str]) -> list[RawWork]:
        out: list[RawWork] = []
        for oid in object_ids:
            try:
                data = self._get(f"{_BASE}/{oid}", params={"fields": _FIELDS})
            except httpx.HTTPStatusError:
                logger.warning("aic: object %s fetch failed", oid)
                continue
            w = _to_work(data.get("data") or {})
            if w is not None:
                out.append(w)
        return out


def _to_work(rec: dict) -> RawWork | None:
    oid = rec.get("id")
    if oid is None:
        return None
    image_id = rec.get("image_id")
    image_url = f"{_IIIF}/{image_id}/full/843,/0/default.jpg" if image_id else None
    thumb_url = f"{_IIIF}/{image_id}/full/200,/0/default.jpg" if image_id else None
    return RawWork(
        source="aic",
        source_object_id=str(oid),
        title=rec.get("title") or "Untitled",
        year=(rec.get("date_display") or None),
        medium=(rec.get("medium_display") or None),
        image_url=image_url,
        thumb_url=thumb_url,
        source_url=f"https://www.artic.edu/artworks/{oid}",
        credit="Art Institute of Chicago · CC0",
        is_public_domain=bool(rec.get("is_public_domain")),
        is_highlight=False,
    )
```

- [ ] **Step 5: Run it green**

Run: `pytest tests/masters/test_aic.py -q` → PASS.

- [ ] **Step 6: Commit**

```bash
git add src/crawler/masters/museums/aic.py tests/masters/test_aic.py tests/fixtures/masters/aic_*.json
git commit -m "feat(masters): Art Institute of Chicago open-access client"
```

---

## Task 4: Work selection (`select.py`)

Filters to public-domain works that have an image, honors explicit `object_ids` order, otherwise ranks auto-pulled results (highlight first, then has-year, then has-thumb) and caps the per-master total.

**Files:**
- Create: `src/crawler/masters/select.py`
- Test: `tests/masters/test_select.py`

- [ ] **Step 1: Write the failing test**

Create `tests/masters/test_select.py`:

```python
from crawler.masters.models import MasterSeed, RawWork, SourceQuery
from crawler.masters.select import select_works


def _work(oid, source="the_met", pd=True, img="https://x/i.jpg", highlight=False, year="1900"):
    return RawWork(
        source=source, source_object_id=oid, title=f"t{oid}", year=year, medium="m",
        image_url=img, thumb_url=img, source_url=f"https://x/{oid}", credit="c",
        is_public_domain=pd, is_highlight=highlight,
    )


class FakeClient:
    def __init__(self, source, by_id=None, by_query=None):
        self.source = source
        self._by_id = by_id or {}
        self._by_query = by_query or []

    def fetch_by_ids(self, ids):
        return [self._by_id[i] for i in ids if i in self._by_id]

    def search_works(self, query, limit):
        return self._by_query[:limit]


def test_explicit_ids_preserved_in_order_and_filtered():
    seed = MasterSeed(
        id="m", name="M", region="foreign", nationality="US", birth_year=None,
        death_year=None, portrait_url=None,
        sources=[SourceQuery(source="the_met", object_ids=["2", "1", "bad"])],
    )
    client = FakeClient("the_met", by_id={
        "1": _work("1"), "2": _work("2"), "bad": _work("bad", pd=False),
    })
    works = select_works(seed, {"the_met": client}, cap=10)
    assert [w.source_object_id for w in works] == ["2", "1"]  # order kept, non-PD dropped


def test_query_results_ranked_highlight_first_and_capped():
    seed = MasterSeed(
        id="m", name="M", region="foreign", nationality="US", birth_year=None,
        death_year=None, portrait_url=None,
        sources=[SourceQuery(source="the_met", query="M")],
    )
    client = FakeClient("the_met", by_query=[
        _work("a", highlight=False), _work("b", highlight=True), _work("c", highlight=False),
    ])
    works = select_works(seed, {"the_met": client}, cap=2)
    assert works[0].source_object_id == "b"  # highlight ranked first
    assert len(works) == 2


def test_dedupes_same_work_id_across_sources():
    seed = MasterSeed(
        id="m", name="M", region="foreign", nationality="US", birth_year=None,
        death_year=None, portrait_url=None,
        sources=[SourceQuery(source="the_met", object_ids=["1"]),
                 SourceQuery(source="the_met", query="M")],
    )
    client = FakeClient("the_met", by_id={"1": _work("1")}, by_query=[_work("1")])
    works = select_works(seed, {"the_met": client}, cap=10)
    assert len(works) == 1
```

- [ ] **Step 2: Run it red**

Run: `pytest tests/masters/test_select.py -q` → FAIL.

- [ ] **Step 3: Implement**

Create `src/crawler/masters/select.py`:

```python
"""Select a master's representative works from their configured museum sources."""

from __future__ import annotations

from crawler.masters.models import MasterSeed, RawWork
from crawler.masters.museums.base import MuseumClient


def _rank_key(w: RawWork) -> tuple:
    # Higher tuple sorts first under reverse=True: highlight, has-year, has-thumb.
    return (w.is_highlight, w.year is not None, w.thumb_url is not None)


def select_works(
    seed: MasterSeed,
    clients: dict[str, MuseumClient],
    cap: int = 10,
) -> list[RawWork]:
    """Gather, filter, rank and cap a master's works.

    Explicit ``object_ids`` keep their authored order and are placed before any
    auto-pulled (query) results. Everything is filtered to public-domain works
    that actually carry an image, and deduped by ``work_id``."""
    explicit: list[RawWork] = []
    pulled: list[RawWork] = []
    for sq in seed.sources:
        client = clients.get(sq.source)
        if client is None:
            continue
        if sq.object_ids:
            explicit.extend(client.fetch_by_ids(sq.object_ids))
        elif sq.query:
            pulled.extend(client.search_works(sq.query, limit=cap))

    pulled.sort(key=_rank_key, reverse=True)

    out: list[RawWork] = []
    seen: set[str] = set()
    for w in [*explicit, *pulled]:
        if not (w.is_public_domain and w.has_image):
            continue
        if w.work_id in seen:
            continue
        seen.add(w.work_id)
        out.append(w)
        if len(out) >= cap:
            break
    return out
```

- [ ] **Step 4: Run it green**

Run: `pytest tests/masters/test_select.py -q` → PASS.

- [ ] **Step 5: Commit**

```bash
git add src/crawler/masters/select.py tests/masters/test_select.py
git commit -m "feat(masters): work selection (PD filter, explicit-id precedence, rank, cap)"
```

---

## Task 5: Gemini text generation method

`commentary.py` needs to *generate* (not translate) Korean prose. Reuse the existing `GeminiTranslator`'s key rotation + retry by adding a generic `generate(prompt)`.

**Files:**
- Modify: `src/crawler/enrich/translator.py` (add `generate` to `GeminiTranslator`)
- Test: `tests/test_translator_generate.py`

- [ ] **Step 1: Write the failing test**

Create `tests/test_translator_generate.py`:

```python
import httpx
import respx

from crawler.enrich.translator import GeminiTranslator


@respx.mock
def test_generate_returns_model_text():
    route = respx.post(
        "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent"
    ).mock(return_value=httpx.Response(200, json={
        "candidates": [{"content": {"parts": [{"text": "생성된 해설"}]}}]
    }))
    t = GeminiTranslator(api_key="k", min_interval=0)
    out = t.generate("write a caption")
    assert out == "생성된 해설"
    assert route.called


@respx.mock
def test_generate_empty_response_returns_empty_string():
    respx.post(
        "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent"
    ).mock(return_value=httpx.Response(200, json={"candidates": []}))
    t = GeminiTranslator(api_key="k", min_interval=0)
    assert t.generate("x") == ""
```

- [ ] **Step 2: Run it red**

Run: `pytest tests/test_translator_generate.py -q` → FAIL (`AttributeError: generate`).

- [ ] **Step 3: Implement**

In `src/crawler/enrich/translator.py`, add this method to `GeminiTranslator` (place it just before `def close`):

```python
    def generate(self, prompt: str, *, temperature: float = 0.4) -> str:
        """Generate free-form text from a prompt (not a translation). Reuses the
        same key rotation + retry/quota handling as translate(). Returns the
        model text, or "" when the response is empty/blocked."""
        if not prompt or not prompt.strip():
            return ""
        key = self._acquire_key()
        data = self._post({
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {"temperature": temperature},
        }, key)
        return self._extract(data).strip()
```

- [ ] **Step 4: Run it green**

Run: `pytest tests/test_translator_generate.py -q` → PASS.

- [ ] **Step 5: Commit**

```bash
git add src/crawler/enrich/translator.py tests/test_translator_generate.py
git commit -m "feat(translator): generic Gemini text generation method"
```

---

## Task 6: Commentary cache (`cache.py`)

Caches generated `{ko,en,ja}` text per id, keyed also by a hash of the facts that prompted it, so unchanged entries are never regenerated and `--reset` can wipe it.

**Files:**
- Create: `src/crawler/masters/cache.py`
- Test: `tests/masters/test_cache.py`

- [ ] **Step 1: Write the failing test**

Create `tests/masters/test_cache.py`:

```python
from crawler.masters.cache import CommentaryCache, LocalizedText


def test_put_get_roundtrip(tmp_path):
    path = tmp_path / "c.json"
    cache = CommentaryCache(path)
    val = LocalizedText(ko="가", en="a", ja="あ")
    cache.put("the_met-1", "hash1", val)
    cache.save()

    reloaded = CommentaryCache(path)
    assert reloaded.get("the_met-1", "hash1") == val


def test_get_miss_on_changed_facts_hash(tmp_path):
    cache = CommentaryCache(tmp_path / "c.json")
    cache.put("k", "hashA", LocalizedText(ko="x", en="x", ja="x"))
    assert cache.get("k", "hashB") is None  # facts changed → regenerate


def test_clear_empties_cache(tmp_path):
    path = tmp_path / "c.json"
    cache = CommentaryCache(path)
    cache.put("k", "h", LocalizedText(ko="x", en="x", ja="x"))
    cache.clear()
    assert cache.get("k", "h") is None
```

- [ ] **Step 2: Run it red**

Run: `pytest tests/masters/test_cache.py -q` → FAIL.

- [ ] **Step 3: Implement**

Create `src/crawler/masters/cache.py`:

```python
"""On-disk cache of generated commentary so reruns don't re-call Gemini."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path


@dataclass(frozen=True)
class LocalizedText:
    ko: str
    en: str
    ja: str


class CommentaryCache:
    """JSON file mapping ``id -> {"facts_hash": str, "text": {ko,en,ja}}``."""

    def __init__(self, path: str | Path) -> None:
        self._path = Path(path)
        self._data: dict[str, dict] = {}
        if self._path.exists():
            try:
                self._data = json.loads(self._path.read_text(encoding="utf-8"))
            except (ValueError, OSError):
                self._data = {}

    def get(self, key: str, facts_hash: str) -> LocalizedText | None:
        entry = self._data.get(key)
        if not entry or entry.get("facts_hash") != facts_hash:
            return None
        t = entry.get("text") or {}
        return LocalizedText(ko=t.get("ko", ""), en=t.get("en", ""), ja=t.get("ja", ""))

    def put(self, key: str, facts_hash: str, value: LocalizedText) -> None:
        self._data[key] = {"facts_hash": facts_hash, "text": asdict(value)}

    def clear(self) -> None:
        self._data = {}

    def save(self) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._path.write_text(
            json.dumps(self._data, ensure_ascii=False, indent=2), encoding="utf-8"
        )
```

- [ ] **Step 4: Run it green**

Run: `pytest tests/masters/test_cache.py -q` → PASS.

- [ ] **Step 5: Commit**

```bash
git add src/crawler/masters/cache.py tests/masters/test_cache.py
git commit -m "feat(masters): commentary cache keyed by id + facts hash"
```

---

## Task 7: Commentary writer (`commentary.py`)

Generates Korean bio/tagline (per master) and Korean commentary (per work) via `generate`, then reuses `translate_batch` for en/ja, caching the result. The Gemini client is injected so tests pass a fake.

**Files:**
- Create: `src/crawler/masters/commentary.py`
- Test: `tests/masters/test_commentary.py`

- [ ] **Step 1: Write the failing test**

Create `tests/masters/test_commentary.py`:

```python
from crawler.masters.cache import CommentaryCache, LocalizedText
from crawler.masters.commentary import CommentaryWriter
from crawler.masters.models import MasterSeed, RawWork


class FakeGemini:
    def __init__(self):
        self.generate_calls = 0

    def generate(self, prompt, *, temperature=0.4):
        self.generate_calls += 1
        return "한국어 본문"

    def translate_batch(self, jobs):
        # jobs: list[(text, src, tgt)] -> echo with a target marker
        return [f"{tgt}:{text}" for (text, _src, tgt) in jobs]


def _seed():
    return MasterSeed(id="atget", name="Eugène Atget", region="foreign",
                      nationality="FR", birth_year=1857, death_year=1927,
                      portrait_url=None, sources=[])


def _work():
    return RawWork(source="the_met", source_object_id="1", title="Le Pont Neuf",
                   year="1900", medium="Albumen", image_url="https://x/i.jpg",
                   thumb_url="https://x/t.jpg", source_url="https://x/1",
                   credit="Met", is_public_domain=True)


def test_master_text_generates_ko_then_translates(tmp_path):
    g = FakeGemini()
    w = CommentaryWriter(g, CommentaryCache(tmp_path / "c.json"))
    out = w.master_text(_seed())
    assert out.ko == "한국어 본문"
    assert out.en == "en:한국어 본문"
    assert out.ja == "ja:한국어 본문"


def test_master_text_cached_second_call_skips_generation(tmp_path):
    g = FakeGemini()
    cache = CommentaryCache(tmp_path / "c.json")
    w = CommentaryWriter(g, cache)
    w.master_text(_seed())
    first = g.generate_calls
    w.master_text(_seed())  # same facts → cache hit
    assert g.generate_calls == first  # no extra generation


def test_work_text_generates_and_translates(tmp_path):
    g = FakeGemini()
    w = CommentaryWriter(g, CommentaryCache(tmp_path / "c.json"))
    out = w.work_text(_work(), master_name="Eugène Atget")
    assert out.ko == "한국어 본문"
    assert out.en.startswith("en:")
```

- [ ] **Step 2: Run it red**

Run: `pytest tests/masters/test_commentary.py -q` → FAIL.

- [ ] **Step 3: Implement**

Create `src/crawler/masters/commentary.py`:

```python
"""Generate finished ko/en/ja editorial text for masters and their works.

Strategy: generate the Korean original with Gemini, then reuse the existing
translator to produce en/ja. Results are cached by a hash of the inputs."""

from __future__ import annotations

import hashlib
from typing import Protocol

from crawler.masters.cache import CommentaryCache, LocalizedText
from crawler.masters.models import MasterSeed, RawWork


class TextEngine(Protocol):
    def generate(self, prompt: str, *, temperature: float = ...) -> str: ...
    def translate_batch(self, jobs: list[tuple[str, str, str]]) -> list[str]: ...


def _hash(*parts: str) -> str:
    return hashlib.sha256("|".join(parts).encode("utf-8")).hexdigest()[:16]


def _master_prompt(seed: MasterSeed) -> str:
    years = f"{seed.birth_year or '?'}–{seed.death_year or '?'}"
    return (
        "당신은 사진사(史) 큐레이터입니다. 아래 사진 거장을 한국어로 소개하는 "
        "글을 쓰세요. 3~4문장으로, 이 작가가 왜 사진사에서 중요한지, 어떤 시선과 "
        "주제를 가졌는지 따뜻하고 읽기 좋은 문체로. 군더더기·인사말·따옴표 없이 "
        "본문만 출력하세요.\n"
        f"작가: {seed.name} ({seed.nationality}, {years})"
    )


def _work_prompt(work: RawWork, master_name: str) -> str:
    facts = ", ".join(p for p in [work.title, work.year, work.medium] if p)
    return (
        "당신은 사진 비평가입니다. 아래 사진 작품을 한국어로 2~3문장 해설하세요. "
        "왜 좋은 사진인지(빛·구도·순간·역사적 의미 등)와 어떤 맥락에서 찍혔는지를 "
        "구체적으로. 인사말·따옴표 없이 본문만 출력하세요.\n"
        f"작가: {master_name}\n작품 정보: {facts}"
    )


class CommentaryWriter:
    def __init__(self, engine: TextEngine, cache: CommentaryCache) -> None:
        self._engine = engine
        self._cache = cache

    def _localize(self, key: str, facts_hash: str, prompt: str) -> LocalizedText:
        hit = self._cache.get(key, facts_hash)
        if hit is not None:
            return hit
        ko = self._engine.generate(prompt)
        en, ja = self._engine.translate_batch([(ko, "ko", "en"), (ko, "ko", "ja")])
        value = LocalizedText(ko=ko, en=en, ja=ja)
        self._cache.put(key, facts_hash, value)
        return value

    def master_text(self, seed: MasterSeed) -> LocalizedText:
        h = _hash("master", seed.name, str(seed.birth_year), str(seed.death_year))
        return self._localize(f"master:{seed.id}", h, _master_prompt(seed))

    def work_text(self, work: RawWork, master_name: str) -> LocalizedText:
        h = _hash("work", work.title, work.year or "", work.medium or "")
        return self._localize(f"work:{work.work_id}", h, _work_prompt(work, master_name))
```

- [ ] **Step 4: Run it green**

Run: `pytest tests/masters/test_commentary.py -q` → PASS.

- [ ] **Step 5: Commit**

```bash
git add src/crawler/masters/commentary.py tests/masters/test_commentary.py
git commit -m "feat(masters): Gemini commentary writer (ko generate + en/ja translate, cached)"
```

---

## Task 8: Build orchestration (`build.py`)

Assembles the masters.json dict from roster + clients + writer, following the `tr` convention (flat = original; ko/ja name + en/ja bio/commentary in `tr`).

**Files:**
- Create: `src/crawler/masters/build.py`
- Test: `tests/masters/test_build.py`

- [ ] **Step 1: Write the failing test**

Create `tests/masters/test_build.py`:

```python
import json
from datetime import UTC, datetime

from crawler.masters.cache import LocalizedText
from crawler.masters.models import MasterSeed, RawWork, SourceQuery


class FakeWriter:
    def master_text(self, seed):
        return LocalizedText(ko=f"{seed.name} 소개", en=f"about {seed.name}", ja=f"{seed.name} 紹介")

    def work_text(self, work, master_name):
        return LocalizedText(ko=f"{work.title} 해설", en=f"about {work.title}", ja=f"{work.title} 解説")


class FakeClient:
    source = "the_met"

    def fetch_by_ids(self, ids):
        return [RawWork(source="the_met", source_object_id=i, title=f"W{i}", year="1900",
                        medium="Albumen", image_url=f"https://x/{i}.jpg",
                        thumb_url=f"https://x/{i}_t.jpg", source_url=f"https://x/{i}",
                        credit="Met · CC0", is_public_domain=True) for i in ids]

    def search_works(self, query, limit):
        return []


def _roster():
    return [MasterSeed(id="atget", name="Eugène Atget", region="foreign", nationality="FR",
                       birth_year=1857, death_year=1927, portrait_url="https://x/a.jpg",
                       sources=[SourceQuery(source="the_met", object_ids=["1"])])]


def test_build_masters_shape():
    from crawler.masters.build import build_masters

    cat = build_masters(
        roster=_roster(), clients={"the_met": FakeClient()}, writer=FakeWriter(),
        generated_at=datetime(2026, 6, 5, tzinfo=UTC), cap=10,
    )
    assert cat["generated_at"].startswith("2026-06-05")
    m = cat["masters"][0]
    assert m["id"] == "atget"
    assert m["name"] == "Eugène Atget"
    assert m["lang"] == "ko"
    assert m["region"] == "foreign"
    assert m["bio"] == "Eugène Atget 소개"  # ko flat
    assert m["tr"]["en"]["bio"] == "about Eugène Atget"
    assert m["tr"]["ja"]["bio"] == "Eugène Atget 紹介"
    assert m["portraitUrl"] == "https://x/a.jpg"

    w = m["works"][0]
    assert w["id"] == "the_met-1"
    assert w["imageUrl"] == "https://x/1.jpg"
    assert w["commentary"] == "W1 해설"  # ko flat
    assert w["tr"]["en"]["commentary"] == "about W1"
    assert w["credit"] == "Met · CC0"


def test_build_masters_drops_master_with_no_works():
    from crawler.masters.build import build_masters

    class Empty(FakeClient):
        def fetch_by_ids(self, ids):
            return []

    cat = build_masters(roster=_roster(), clients={"the_met": Empty()},
                        writer=FakeWriter(), generated_at=datetime(2026, 6, 5, tzinfo=UTC))
    assert cat["masters"] == []  # a master with zero usable works is omitted
```

- [ ] **Step 2: Run it red**

Run: `pytest tests/masters/test_build.py -q` → FAIL.

- [ ] **Step 3: Implement**

Create `src/crawler/masters/build.py`:

```python
"""Assemble masters.json from the roster, museum clients and the writer."""

from __future__ import annotations

import json
import logging
import os
from datetime import datetime

from crawler.masters.cache import LocalizedText
from crawler.masters.commentary import CommentaryWriter
from crawler.masters.models import MasterSeed, RawWork
from crawler.masters.museums.base import MuseumClient
from crawler.masters.select import select_works

logger = logging.getLogger(__name__)

DEFAULT_OUTPUT = "web/public/data/masters.json"


def _work_json(work: RawWork, text: LocalizedText) -> dict:
    return {
        "id": work.work_id,
        "title": work.title,
        "year": work.year,
        "medium": work.medium,
        "imageUrl": work.image_url,
        "thumbUrl": work.thumb_url,
        "source": work.source,
        "sourceUrl": work.source_url,
        "credit": work.credit,
        "commentary": text.ko,  # ko flat
        "tr": {"en": {"commentary": text.en}, "ja": {"commentary": text.ja}},
    }


def build_masters(
    roster: list[MasterSeed],
    clients: dict[str, MuseumClient],
    writer: CommentaryWriter,
    generated_at: datetime,
    cap: int = 10,
) -> dict:
    masters: list[dict] = []
    for seed in roster:
        works = select_works(seed, clients, cap=cap)
        if not works:
            logger.warning("masters: %s has no usable works; skipping", seed.id)
            continue
        mt = writer.master_text(seed)
        work_jsons = [_work_json(w, writer.work_text(w, seed.name)) for w in works]
        masters.append({
            "id": seed.id,
            "name": seed.name,
            "lang": "ko",
            "region": seed.region,
            "nationality": seed.nationality,
            "birthYear": seed.birth_year,
            "deathYear": seed.death_year,
            "tagline": mt.ko_tagline,
            "bio": mt.ko,
            "portraitUrl": seed.portrait_url,
            "tr": {
                "en": {"tagline": mt.en_tagline, "bio": mt.en},
                "ja": {"tagline": mt.ja_tagline, "bio": mt.ja},
            },
            "works": work_jsons,
        })
    return {"generated_at": generated_at.isoformat(), "masters": masters}


def write_masters(catalog: dict, path: str = DEFAULT_OUTPUT) -> int:
    parent = os.path.dirname(path)
    if parent:
        os.makedirs(parent, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(catalog, f, ensure_ascii=False, indent=2, allow_nan=False)
    return len(catalog["masters"])
```

NOTE: the test above does not assert taglines, so to keep `LocalizedText` minimal the
writer must also expose tagline fields. **Update `LocalizedText`** in
`src/crawler/masters/cache.py` to carry taglines, and the writer to fill them. Specifically:

1. In `cache.py`, extend the dataclass:

```python
@dataclass(frozen=True)
class LocalizedText:
    ko: str
    en: str
    ja: str
    ko_tagline: str = ""
    en_tagline: str = ""
    ja_tagline: str = ""
```

2. In `commentary.py`, change `master_text` to also produce a one-line tagline. Replace
the body of `master_text` with:

```python
    def master_text(self, seed: MasterSeed) -> LocalizedText:
        h = _hash("master", seed.name, str(seed.birth_year), str(seed.death_year))
        hit = self._cache.get(f"master:{seed.id}", h)
        if hit is not None:
            return hit
        bio_ko = self._engine.generate(_master_prompt(seed))
        tag_ko = self._engine.generate(_tagline_prompt(seed))
        en_bio, ja_bio, en_tag, ja_tag = self._engine.translate_batch([
            (bio_ko, "ko", "en"), (bio_ko, "ko", "ja"),
            (tag_ko, "ko", "en"), (tag_ko, "ko", "ja"),
        ])
        value = LocalizedText(ko=bio_ko, en=en_bio, ja=ja_bio,
                              ko_tagline=tag_ko, en_tagline=en_tag, ja_tagline=ja_tag)
        self._cache.put(f"master:{seed.id}", h, value)
        return value
```

and add the tagline prompt helper:

```python
def _tagline_prompt(seed: MasterSeed) -> str:
    return (
        "아래 사진 거장을 한 줄(15자 내외)로 표현하는 한국어 태그라인을 쓰세요. "
        "예: '파리를 기록한 사진의 선구자'. 따옴표·군더더기 없이 한 줄만.\n"
        f"작가: {seed.name}"
    )
```

3. The `work_text` localization keeps `ko_tagline`/`en_tagline`/`ja_tagline` empty (default).
Since `_localize` builds a `LocalizedText` without taglines, leave `work_text` using the
existing `_localize` helper unchanged.

Also update the **Task 7 test** `test_master_text_generates_ko_then_translates` expectation:
`master_text` now calls `generate` twice (bio + tagline) and `translate_batch` once with 4
jobs returning `["en:…","ja:…","en:…","ja:…"]`; assert `out.ko == "한국어 본문"`,
`out.ko_tagline == "한국어 본문"`, `out.en == "en:한국어 본문"`. (The FakeGemini returns the
same text for every `generate`, so bio and tagline are equal in the test — that's fine.)

- [ ] **Step 4: Run it green**

Run: `pytest tests/masters/ -q` → PASS (all masters tests, including the updated Task 7 test).

- [ ] **Step 5: Commit**

```bash
git add src/crawler/masters/build.py src/crawler/masters/cache.py src/crawler/masters/commentary.py tests/masters/
git commit -m "feat(masters): build masters.json (tr convention) + taglines"
```

---

## Task 9: Roster seed data (`roster.py`)

The curated MVP roster (~12–20 masters). Each entry's `object_ids` should be filled with PD object ids verified via the museum APIs; where ids aren't hand-verified yet, a `query` auto-pulls.

**Files:**
- Create: `src/crawler/masters/roster.py`
- Test: `tests/masters/test_roster.py`

- [ ] **Step 1: Write the failing test**

Create `tests/masters/test_roster.py`:

```python
from crawler.masters.models import MasterSeed
from crawler.masters.roster import ROSTER


def test_roster_nonempty_and_well_formed():
    assert len(ROSTER) >= 8
    ids = [m.id for m in ROSTER]
    assert len(ids) == len(set(ids)), "master ids must be unique"
    for m in ROSTER:
        assert isinstance(m, MasterSeed)
        assert m.region in {"kr", "jp", "foreign"}
        assert m.sources, f"{m.id} has no sources"
        for sq in m.sources:
            assert sq.source in {"the_met", "aic"}
            assert bool(sq.query) ^ bool(sq.object_ids), "exactly one of query/object_ids"


def test_roster_covers_all_three_regions():
    regions = {m.region for m in ROSTER}
    assert {"kr", "jp", "foreign"} <= regions
```

- [ ] **Step 2: Run it red**

Run: `pytest tests/masters/test_roster.py -q` → FAIL.

- [ ] **Step 3: Implement**

Create `src/crawler/masters/roster.py`. Start from this list; fill/verify `object_ids` by
running the museum search (Task 2/3 clients) for each artist and picking PD, image-bearing
iconic works. Where verification is pending, leave a `query` entry (auto-pull). Portrait URLs
are PD images from Wikimedia Commons — open each master's Commons page and copy a direct
`upload.wikimedia.org/...` file URL.

```python
"""Curated roster of public-domain photography masters (MVP).

Foreign classic masters form the backbone; a few early Korean/Japanese figures
are included where public-domain images exist. Fill object_ids with verified PD
object ids; until verified, a query auto-pulls from the museum API."""

from __future__ import annotations

from crawler.masters.models import MasterSeed, SourceQuery

ROSTER: list[MasterSeed] = [
    MasterSeed(
        id="eugene-atget", name="Eugène Atget", region="foreign", nationality="FR",
        birth_year=1857, death_year=1927,
        portrait_url="https://upload.wikimedia.org/wikipedia/commons/0/0a/Eugene_Atget.jpg",
        sources=[SourceQuery(source="the_met", query="Eugène Atget"),
                 SourceQuery(source="aic", query="Eugène Atget")],
    ),
    MasterSeed(
        id="julia-margaret-cameron", name="Julia Margaret Cameron", region="foreign",
        nationality="GB", birth_year=1815, death_year=1879, portrait_url=None,
        sources=[SourceQuery(source="the_met", query="Julia Margaret Cameron")],
    ),
    MasterSeed(
        id="alfred-stieglitz", name="Alfred Stieglitz", region="foreign", nationality="US",
        birth_year=1864, death_year=1946, portrait_url=None,
        sources=[SourceQuery(source="the_met", query="Alfred Stieglitz"),
                 SourceQuery(source="aic", query="Alfred Stieglitz")],
    ),
    MasterSeed(
        id="dorothea-lange", name="Dorothea Lange", region="foreign", nationality="US",
        birth_year=1895, death_year=1965, portrait_url=None,
        sources=[SourceQuery(source="the_met", query="Dorothea Lange")],
    ),
    MasterSeed(
        id="walker-evans", name="Walker Evans", region="foreign", nationality="US",
        birth_year=1903, death_year=1975, portrait_url=None,
        sources=[SourceQuery(source="the_met", query="Walker Evans"),
                 SourceQuery(source="aic", query="Walker Evans")],
    ),
    MasterSeed(
        id="timothy-osullivan", name="Timothy H. O'Sullivan", region="foreign",
        nationality="US", birth_year=1840, death_year=1882, portrait_url=None,
        sources=[SourceQuery(source="the_met", query="Timothy O'Sullivan")],
    ),
    MasterSeed(
        id="carleton-watkins", name="Carleton Watkins", region="foreign", nationality="US",
        birth_year=1829, death_year=1916, portrait_url=None,
        sources=[SourceQuery(source="the_met", query="Carleton Watkins")],
    ),
    MasterSeed(
        id="nadar", name="Nadar (Gaspard-Félix Tournachon)", region="foreign",
        nationality="FR", birth_year=1820, death_year=1910, portrait_url=None,
        sources=[SourceQuery(source="the_met", query="Nadar")],
    ),
    MasterSeed(
        id="felice-beato", name="Felice Beato", region="jp", nationality="IT",
        birth_year=1832, death_year=1909, portrait_url=None,
        sources=[SourceQuery(source="the_met", query="Felice Beato")],
    ),
    MasterSeed(
        id="kusakabe-kimbei", name="Kusakabe Kimbei (日下部金兵衛)", region="jp",
        nationality="JP", birth_year=1841, death_year=1934, portrait_url=None,
        sources=[SourceQuery(source="the_met", query="Kusakabe Kimbei")],
    ),
    MasterSeed(
        id="adolfo-farsari", name="Adolfo Farsari", region="jp", nationality="IT",
        birth_year=1841, death_year=1898, portrait_url=None,
        sources=[SourceQuery(source="the_met", query="Adolfo Farsari")],
    ),
    MasterSeed(
        id="raimund-von-stillfried", name="Raimund von Stillfried", region="jp",
        nationality="AT", birth_year=1839, death_year=1911, portrait_url=None,
        sources=[SourceQuery(source="the_met", query="Stillfried")],
    ),
    # Early Korea photography is sparse in CC0 collections; these query the Met's
    # 19th-c "Korea" holdings and are kept only if usable PD works come back.
    MasterSeed(
        id="early-korea-photography", name="조선 풍경 사진 (19c)", region="kr",
        nationality="KR", birth_year=None, death_year=None, portrait_url=None,
        sources=[SourceQuery(source="the_met", query="Korea photograph")],
    ),
]
```

- [ ] **Step 4: Run it green**

Run: `pytest tests/masters/test_roster.py -q` → PASS.

- [ ] **Step 5: Commit**

```bash
git add src/crawler/masters/roster.py tests/masters/test_roster.py
git commit -m "feat(masters): curated MVP roster seed"
```

---

## Task 10: CLI command `build-masters`

**Files:**
- Modify: `src/crawler/cli.py`
- Test: `tests/masters/test_cli_build_masters.py`

- [ ] **Step 1: Write the failing test**

Create `tests/masters/test_cli_build_masters.py`:

```python
from typer.testing import CliRunner

from crawler.cli import app

runner = CliRunner()


def test_build_masters_command_registered():
    result = runner.invoke(app, ["build-masters", "--help"])
    assert result.exit_code == 0
    assert "masters.json" in result.output or "masters" in result.output
```

- [ ] **Step 2: Run it red**

Run: `pytest tests/masters/test_cli_build_masters.py -q` → FAIL (no such command).

- [ ] **Step 3: Implement**

In `src/crawler/cli.py`, add this command (after the `backfill_translations_cmd`, before `def main`):

```python
@app.command("build-masters")
def build_masters_cmd(
    output: str = "web/public/data/masters.json",
    cache_path: str = ".cache/masters_commentary.json",
    cap: int = 10,
    reset: bool = False,
) -> None:
    """Build the 거장의 시선 masters.json from the curated roster + museum APIs.

    Pulls public-domain works from The Met / AIC, writes ko/en/ja commentary with
    Gemini (cached), and emits masters.json for the web app. --reset clears the
    commentary cache and regenerates everything."""
    from crawler.enrich.translator import GeminiTranslator
    from crawler.masters.build import build_masters, write_masters
    from crawler.masters.cache import CommentaryCache
    from crawler.masters.commentary import CommentaryWriter
    from crawler.masters.museums.aic import AicClient
    from crawler.masters.museums.the_met import MetClient
    from crawler.masters.roster import ROSTER

    engine = GeminiTranslator.from_env()
    cache = CommentaryCache(cache_path)
    if reset:
        cache.clear()
    writer = CommentaryWriter(engine, cache)
    clients = {"the_met": MetClient(), "aic": AicClient()}
    catalog = build_masters(
        roster=ROSTER, clients=clients, writer=writer,
        generated_at=datetime.now(UTC), cap=cap,
    )
    cache.save()
    count = write_masters(catalog, output)
    typer.echo(f"wrote {count} masters to {output}")
```

(`datetime`, `UTC`, and `typer` are already imported at the top of `cli.py`.)

- [ ] **Step 4: Run it green**

Run: `pytest tests/masters/test_cli_build_masters.py -q` → PASS.

- [ ] **Step 5: Commit**

```bash
git add src/crawler/cli.py tests/masters/test_cli_build_masters.py
git commit -m "feat(masters): build-masters CLI command"
```

---

## Task 11: Generate the real masters.json (manual data run)

This is a one-time live run (needs network + `GEMINI_API_KEY`). It produces the committed
data the web app reads. On the free Gemini tier this may not finish all masters in one run;
rerun until it converges (the cache makes reruns cheap).

- [ ] **Step 1: Verify roster object ids resolve** (optional but recommended)

```bash
source .venv/bin/activate
python - <<'PY'
from crawler.masters.museums.the_met import MetClient
from crawler.masters.museums.aic import AicClient
from crawler.masters.roster import ROSTER
from crawler.masters.select import select_works
clients = {"the_met": MetClient(), "aic": AicClient()}
for m in ROSTER:
    works = select_works(m, clients, cap=10)
    print(f"{m.id:30s} {len(works)} works")
PY
```
Drop or re-query any master that returns 0 works (edit `roster.py`).

- [ ] **Step 2: Build with Gemini**

```bash
export GEMINI_API_KEY=...   # your key(s)
crawler build-masters --reset
```
Re-run `crawler build-masters` (no `--reset`) if it stops early on a daily quota block until
`web/public/data/masters.json` contains all rostered masters with non-empty ko/en/ja text.

- [ ] **Step 3: Sanity-check the output**

```bash
python -c "import json;d=json.load(open('web/public/data/masters.json'));print(len(d['masters']),'masters');import itertools;print(sum(len(m['works']) for m in d['masters']),'works')"
```
Expect ≥8 masters, each with ≥1 work, ko/en/ja text present.

- [ ] **Step 4: Commit the data**

```bash
git add web/public/data/masters.json
git commit -m "data(masters): initial masters.json (거장의 시선)"
```

---

## Task 12: GitHub Actions workflow `build-masters.yml`

**Files:**
- Create: `.github/workflows/build-masters.yml`

- [ ] **Step 1: Create the workflow**

Create `.github/workflows/build-masters.yml` (mirror the python setup used in
`.github/workflows/crawl.yml` — confirm the Python version + install command there and match
it):

```yaml
name: build-masters

on:
  workflow_dispatch:
  schedule:
    - cron: "0 4 1 * *"  # 1st of each month, 04:00 UTC

jobs:
  build:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.12"
      - run: pip install -e ".[dev]"
      - name: Build masters.json
        env:
          GEMINI_API_KEY: ${{ secrets.GEMINI_API_KEY }}
          GEMINI_MODEL: ${{ vars.GEMINI_MODEL }}
        run: crawler build-masters
      - name: Commit changes
        run: |
          git config user.name "github-actions[bot]"
          git config user.email "github-actions[bot]@users.noreply.github.com"
          git add web/public/data/masters.json
          git diff --cached --quiet || git commit -m "data(masters): refresh masters.json"
          git push
```

- [ ] **Step 2: Verify YAML + commit**

Run: `python -c "import yaml,sys; yaml.safe_load(open('.github/workflows/build-masters.yml'))"` → no error.

```bash
git add .github/workflows/build-masters.yml
git commit -m "ci(masters): monthly + manual build-masters workflow"
```

---

## Task 13: Web masters catalog lib (`masters.ts`)

**Files:**
- Create: `web/src/lib/masters.ts`
- Test: `web/src/lib/masters.test.ts`

- [ ] **Step 1: Write the failing test**

Create `web/src/lib/masters.test.ts`:

```ts
import { describe, expect, it } from "vitest";
import { parseMasters } from "./masters";

const raw = {
  generated_at: "2026-06-05T00:00:00Z",
  masters: [
    {
      id: "atget", name: "Eugène Atget", lang: "ko", region: "foreign",
      nationality: "FR", birthYear: 1857, deathYear: 1927,
      tagline: "파리를 기록한 선구자", bio: "소개", portraitUrl: "https://x/a.jpg",
      tr: { en: { tagline: "Pioneer", bio: "about" }, ja: { name: "アジェ" } },
      works: [{
        id: "the_met-1", title: "Le Pont Neuf", year: "1900", medium: "Albumen",
        imageUrl: "https://x/1.jpg", thumbUrl: "https://x/1t.jpg", source: "the_met",
        sourceUrl: "https://x/1", credit: "Met · CC0", commentary: "해설",
        tr: { en: { commentary: "about" } },
      }],
    },
  ],
};

describe("parseMasters", () => {
  it("maps masters and works", () => {
    const cat = parseMasters(raw);
    expect(cat.masters).toHaveLength(1);
    const m = cat.masters[0];
    expect(m.id).toBe("atget");
    expect(m.region).toBe("foreign");
    expect(m.works[0].imageUrl).toBe("https://x/1.jpg");
    expect(m.tr.ja?.name).toBe("アジェ");
  });

  it("tolerates missing fields", () => {
    const cat = parseMasters({ generated_at: "x", masters: [{ id: "a", name: "A", works: [] }] });
    expect(cat.masters[0].works).toEqual([]);
    expect(cat.masters[0].region).toBe("foreign");
  });
});
```

- [ ] **Step 2: Run it red**

Run (in `web/`): `npx vitest run src/lib/masters.test.ts` → FAIL.

- [ ] **Step 3: Implement**

Create `web/src/lib/masters.ts`:

```ts
import type { Locale } from "@/lib/i18n";
import type { TrMap } from "@/lib/catalog";

export type Region = "kr" | "jp" | "foreign";

export interface MasterWork {
  id: string;
  title: string;
  year: string | null;
  medium: string | null;
  imageUrl: string | null;
  thumbUrl: string | null;
  source: string | null;
  sourceUrl: string | null;
  credit: string | null;
  commentary: string | null;
  lang: string | null;
  tr: TrMap;
}

export interface Master {
  id: string;
  name: string;
  region: Region;
  nationality: string | null;
  birthYear: number | null;
  deathYear: number | null;
  tagline: string | null;
  bio: string | null;
  portraitUrl: string | null;
  lang: string | null;
  tr: TrMap;
  works: MasterWork[];
}

export interface MastersCatalog {
  generatedAt: string;
  masters: Master[];
}

/* eslint-disable @typescript-eslint/no-explicit-any */

function trOf(v: any): TrMap {
  return v && typeof v === "object" ? (v as TrMap) : {};
}

function parseWork(w: any): MasterWork {
  return {
    id: w.id, title: w.title ?? "", year: w.year ?? null, medium: w.medium ?? null,
    imageUrl: w.imageUrl ?? null, thumbUrl: w.thumbUrl ?? w.imageUrl ?? null,
    source: w.source ?? null, sourceUrl: w.sourceUrl ?? null, credit: w.credit ?? null,
    commentary: w.commentary ?? null, lang: w.lang ?? "ko", tr: trOf(w.tr),
  };
}

export function parseMasters(raw: any): MastersCatalog {
  return {
    generatedAt: raw.generated_at ?? raw.generatedAt ?? "",
    masters: (raw.masters ?? []).map((m: any): Master => ({
      id: m.id, name: m.name ?? "", region: (m.region ?? "foreign") as Region,
      nationality: m.nationality ?? null, birthYear: m.birthYear ?? null,
      deathYear: m.deathYear ?? null, tagline: m.tagline ?? null, bio: m.bio ?? null,
      portraitUrl: m.portraitUrl ?? null, lang: m.lang ?? "ko", tr: trOf(m.tr),
      works: (m.works ?? []).map(parseWork),
    })),
  };
}

export async function loadMasters(): Promise<MastersCatalog> {
  const data = (await import("../../public/data/masters.json")).default;
  return parseMasters(data);
}

// Convenience: the image to show for a master in lists/carousels — portrait if
// present, else the first work's image.
export function masterFaceImage(m: Master): string | null {
  return m.portraitUrl ?? m.works.find((w) => w.thumbUrl || w.imageUrl)?.thumbUrl ?? null;
}

export function masterHeroImage(m: Master): string | null {
  return m.works.find((w) => w.imageUrl)?.imageUrl ?? m.portraitUrl ?? null;
}
```

- [ ] **Step 4: Run it green**

Run (in `web/`): `npx vitest run src/lib/masters.test.ts` → PASS.

- [ ] **Step 5: Commit**

```bash
git add web/src/lib/masters.ts web/src/lib/masters.test.ts
git commit -m "feat(web): masters catalog lib (parse + load + image helpers)"
```

---

## Task 14: i18n keys for masters

**Files:**
- Modify: `web/src/lib/i18n.ts`

- [ ] **Step 1: Add keys to all three dicts**

In `web/src/lib/i18n.ts`, add these entries. Find the `const ko: Dict = {` block and add
inside it:

```ts
  "masters.title": "거장의 시선",
  "masters.subtitle": "사진의 거장들, 그리고 왜 위대한가",
  "masters.regionKr": "한국",
  "masters.regionJp": "일본",
  "masters.regionForeign": "해외",
  "masters.whyGreat": "왜 좋은 사진인가",
  "masters.source": "출처",
  "masters.viewOriginal": "원본 보기",
  "masters.years": "{birth}–{death}",
```

In the `const en: Dict = {` block add:

```ts
  "masters.title": "The Master's Gaze",
  "masters.subtitle": "Masters of photography — and why they matter",
  "masters.regionKr": "Korea",
  "masters.regionJp": "Japan",
  "masters.regionForeign": "International",
  "masters.whyGreat": "Why it's a great photograph",
  "masters.source": "Source",
  "masters.viewOriginal": "View original",
  "masters.years": "{birth}–{death}",
```

In the `const ja: Dict = {` block add:

```ts
  "masters.title": "巨匠のまなざし",
  "masters.subtitle": "写真の巨匠たち、そしてその偉大さ",
  "masters.regionKr": "韓国",
  "masters.regionJp": "日本",
  "masters.regionForeign": "海外",
  "masters.whyGreat": "なぜ優れた写真なのか",
  "masters.source": "出典",
  "masters.viewOriginal": "オリジナルを見る",
  "masters.years": "{birth}–{death}",
```

- [ ] **Step 2: Verify + commit**

Run (in `web/`): `npm run lint` → no new errors.

```bash
git add web/src/lib/i18n.ts
git commit -m "feat(web): i18n keys for 거장의 시선"
```

---

## Task 15: Carousel slide builder (`carousel.ts`)

A pure, seedable function that mixes featured-exhibition slides and randomized master
slides — so randomization is unit-testable.

**Files:**
- Create: `web/src/lib/carousel.ts`
- Test: `web/src/lib/carousel.test.ts`

- [ ] **Step 1: Write the failing test**

Create `web/src/lib/carousel.test.ts`:

```ts
import { describe, expect, it } from "vitest";
import { buildCarouselSlides } from "./carousel";
import type { Master } from "./masters";

function master(id: string): Master {
  return {
    id, name: id, region: "foreign", nationality: "US", birthYear: 1900, deathYear: 1980,
    tagline: "t", bio: "b", portraitUrl: `https://x/${id}.jpg`, lang: "ko", tr: {},
    works: [{ id: `${id}-1`, title: "w", year: "1900", medium: "m",
      imageUrl: `https://x/${id}-1.jpg`, thumbUrl: `https://x/${id}-1t.jpg`,
      source: "the_met", sourceUrl: "https://x/1", credit: "c", commentary: "c",
      lang: "ko", tr: {} }],
  };
}

// deterministic RNG for tests
function seeded(seq: number[]): () => number {
  let i = 0;
  return () => seq[i++ % seq.length];
}

const exhibitions = [{ id: "e1" }, { id: "e2" }] as any[];

describe("buildCarouselSlides", () => {
  it("includes exhibition slides and master slides", () => {
    const slides = buildCarouselSlides(exhibitions, [master("a"), master("b")], {
      masterCount: 2, rng: seeded([0]),
    });
    const kinds = slides.map((s) => s.kind);
    expect(kinds).toContain("exhibition");
    expect(kinds).toContain("master");
  });

  it("limits master slides to masterCount and only uses ones with an image", () => {
    const noImg = master("z");
    noImg.portraitUrl = null;
    noImg.works = [];
    const slides = buildCarouselSlides([], [master("a"), master("b"), noImg], {
      masterCount: 2, rng: seeded([0]),
    });
    const masterSlides = slides.filter((s) => s.kind === "master");
    expect(masterSlides).toHaveLength(2);
    expect(masterSlides.every((s) => s.kind === "master" && s.image)).toBe(true);
  });

  it("is randomized by rng (different seed → different first master)", () => {
    const ms = [master("a"), master("b"), master("c"), master("d")];
    const first = buildCarouselSlides([], ms, { masterCount: 1, rng: seeded([0]) })
      .find((s) => s.kind === "master");
    const second = buildCarouselSlides([], ms, { masterCount: 1, rng: seeded([0.99]) })
      .find((s) => s.kind === "master");
    expect(first?.id).not.toBe(second?.id);
  });
});
```

- [ ] **Step 2: Run it red**

Run (in `web/`): `npx vitest run src/lib/carousel.test.ts` → FAIL.

- [ ] **Step 3: Implement**

Create `web/src/lib/carousel.ts`:

```ts
import type { Master } from "@/lib/masters";
import { masterFaceImage, masterHeroImage } from "@/lib/masters";

export interface ExhibitionSlide {
  kind: "exhibition";
  id: string;
  exhibition: unknown; // the caller's Exhibition; kept opaque here
}

export interface MasterSlide {
  kind: "master";
  id: string;
  name: string;
  tagline: string | null;
  image: string;        // representative work (background)
  face: string | null;  // portrait
}

export type CarouselSlide = ExhibitionSlide | MasterSlide;

export interface BuildOptions {
  masterCount?: number;
  rng?: () => number; // returns [0,1); defaults to Math.random
}

// Fisher–Yates using the injected rng so tests are deterministic.
function shuffle<T>(items: T[], rng: () => number): T[] {
  const a = [...items];
  for (let i = a.length - 1; i > 0; i--) {
    const j = Math.floor(rng() * (i + 1));
    [a[i], a[j]] = [a[j], a[i]];
  }
  return a;
}

export function buildCarouselSlides(
  exhibitions: Array<{ id: string }>,
  masters: Master[],
  opts: BuildOptions = {},
): CarouselSlide[] {
  const rng = opts.rng ?? Math.random;
  const masterCount = opts.masterCount ?? 6;

  const exhibitionSlides: ExhibitionSlide[] = exhibitions.map((e) => ({
    kind: "exhibition", id: e.id, exhibition: e,
  }));

  const usable = masters.filter((m) => masterHeroImage(m));
  const masterSlides: MasterSlide[] = shuffle(usable, rng)
    .slice(0, masterCount)
    .map((m) => ({
      kind: "master", id: m.id, name: m.name, tagline: m.tagline,
      image: masterHeroImage(m) as string, face: masterFaceImage(m),
    }));

  // Interleave so masters and exhibitions alternate where possible, then keep
  // any leftovers. The whole sequence is shuffled by rng for variety per load.
  return shuffle([...exhibitionSlides, ...masterSlides], rng);
}
```

- [ ] **Step 4: Run it green**

Run (in `web/`): `npx vitest run src/lib/carousel.test.ts` → PASS. If the "different seed"
test is flaky for a given seed pair, adjust the seeds in the test until the two seeds map to
different first picks (the builder is correct; the test just needs two distinguishing seeds).

- [ ] **Step 5: Commit**

```bash
git add web/src/lib/carousel.ts web/src/lib/carousel.test.ts
git commit -m "feat(web): seedable carousel slide builder (exhibitions + random masters)"
```

---

## Task 16: `FeaturedCarousel` component

Auto-advances every 1.4s, pauses on hover/focus, disables auto-advance under
`prefers-reduced-motion`. Master slide → `/masters/[id]`; exhibition slide → reuses the
existing hero look and links to `/exhibitions/[id]`.

**Files:**
- Create: `web/src/components/FeaturedCarousel.tsx`
- Test: `web/src/components/FeaturedCarousel.test.tsx`

- [ ] **Step 1: Write the failing test**

Create `web/src/components/FeaturedCarousel.test.tsx`:

```tsx
import { describe, expect, it, vi, beforeEach, afterEach } from "vitest";
import { render, screen, act } from "@testing-library/react";
import { LangProvider } from "@/test/lang";
import { FeaturedCarousel } from "./FeaturedCarousel";
import type { Master } from "@/lib/masters";

function master(id: string): Master {
  return {
    id, name: `Name-${id}`, region: "foreign", nationality: "FR", birthYear: 1857,
    deathYear: 1927, tagline: "tag", bio: "bio", portraitUrl: `https://x/${id}.jpg`,
    lang: "ko", tr: {},
    works: [{ id: `${id}-1`, title: "w", year: "1900", medium: "m",
      imageUrl: `https://x/${id}-1.jpg`, thumbUrl: `https://x/${id}-1t.jpg`,
      source: "the_met", sourceUrl: "https://x/1", credit: "c", commentary: "c",
      lang: "ko", tr: {} }],
  };
}

describe("FeaturedCarousel", () => {
  beforeEach(() => vi.useFakeTimers());
  afterEach(() => vi.useRealTimers());

  it("renders a master slide with the master name", () => {
    render(
      <LangProvider>
        <FeaturedCarousel exhibitions={[]} masters={[master("a")]} rng={() => 0} />
      </LangProvider>,
    );
    expect(screen.getByText("Name-a")).toBeInTheDocument();
  });

  it("advances to the next slide after 1.4s", () => {
    render(
      <LangProvider>
        <FeaturedCarousel exhibitions={[]} masters={[master("a"), master("b")]}
          rng={() => 0} masterCount={2} />
      </LangProvider>,
    );
    const firstActive = screen.getByTestId("carousel-active").textContent;
    act(() => { vi.advanceTimersByTime(1400); });
    const nextActive = screen.getByTestId("carousel-active").textContent;
    expect(nextActive).not.toBe(firstActive);
  });
});
```

NOTE: confirm the existing test helper export name in `web/src/test/lang.tsx` (the home/
component tests already use it). If it exports `LanguageProvider` rather than `LangProvider`,
import that name instead and wrap with it.

- [ ] **Step 2: Run it red**

Run (in `web/`): `npx vitest run src/components/FeaturedCarousel.test.tsx` → FAIL.

- [ ] **Step 3: Implement**

Create `web/src/components/FeaturedCarousel.tsx`:

```tsx
"use client";
import { useEffect, useMemo, useRef, useState } from "react";
import Link from "next/link";
import { PosterImage } from "@/components/PosterImage";
import { useLang } from "@/components/LanguageProvider";
import { buildCarouselSlides, type CarouselSlide } from "@/lib/carousel";
import type { Master } from "@/lib/masters";
import type { Exhibition } from "@/lib/catalog";

const ADVANCE_MS = 1400;

function prefersReducedMotion(): boolean {
  return typeof window !== "undefined"
    && window.matchMedia?.("(prefers-reduced-motion: reduce)").matches === true;
}

export function FeaturedCarousel({
  exhibitions,
  masters,
  masterCount = 6,
  rng,
}: {
  exhibitions: Exhibition[];
  masters: Master[];
  masterCount?: number;
  rng?: () => number;
}) {
  const { t } = useLang();
  // Build the slide list once per mount so it stays stable while advancing, but
  // is reshuffled (random masters) on each fresh load.
  const slides = useMemo<CarouselSlide[]>(
    () => buildCarouselSlides(exhibitions, masters, { masterCount, rng }),
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [],
  );
  const [index, setIndex] = useState(0);
  const [paused, setPaused] = useState(false);
  const reduced = useRef(false);
  useEffect(() => { reduced.current = prefersReducedMotion(); }, []);

  useEffect(() => {
    if (slides.length <= 1 || paused || reduced.current) return;
    const id = setInterval(() => setIndex((i) => (i + 1) % slides.length), ADVANCE_MS);
    return () => clearInterval(id);
  }, [slides.length, paused]);

  if (slides.length === 0) return null;
  const active = slides[index % slides.length];

  return (
    <section
      className="relative mb-9 min-h-[320px] overflow-hidden rounded border border-line"
      onMouseEnter={() => setPaused(true)}
      onMouseLeave={() => setPaused(false)}
      onFocusCapture={() => setPaused(true)}
      onBlurCapture={() => setPaused(false)}
      aria-roledescription="carousel"
    >
      <span data-testid="carousel-active" className="sr-only">{active.id}</span>
      {active.kind === "master" ? (
        <Link href={`/masters/${active.id}`} className="absolute inset-0">
          <PosterImage src={active.image} alt={active.name} />
          <div className="absolute inset-x-0 bottom-0 bg-gradient-to-t from-black/90 to-transparent p-6">
            <div className="text-[11px] font-semibold uppercase tracking-widest text-tx2">
              {t("masters.title")}
            </div>
            <div className="mt-2 flex items-center gap-3">
              {active.face && (
                // eslint-disable-next-line @next/next/no-img-element
                <img src={active.face} alt={active.name}
                  className="h-12 w-12 rounded-full object-cover ring-1 ring-white/30" />
              )}
              <div>
                <h2 className="text-2xl font-extrabold tracking-tight">{active.name}</h2>
                {active.tagline && <div className="mt-1 text-sm text-tx2">{active.tagline}</div>}
              </div>
            </div>
          </div>
        </Link>
      ) : (
        <ExhibitionCarouselSlide exhibition={active.exhibition as Exhibition} />
      )}

      <div className="absolute right-4 top-4 flex gap-1">
        {slides.map((s, i) => (
          <span key={s.id} aria-hidden="true"
            className={`h-1.5 w-1.5 rounded-full ${i === index ? "bg-white" : "bg-white/40"}`} />
        ))}
      </div>
    </section>
  );
}

function ExhibitionCarouselSlide({ exhibition: e }: { exhibition: Exhibition }) {
  const { t } = useLang();
  return (
    <Link href={`/exhibitions/${e.id}`} className="absolute inset-0">
      <PosterImage src={e.posterImageUrl} alt={e.title} />
      <div className="absolute inset-x-0 bottom-0 bg-gradient-to-t from-black/90 to-transparent p-6">
        <div className="text-[11px] font-semibold uppercase tracking-widest text-tx2">{t("home.featured")}</div>
        <h2 className="mt-2 text-2xl font-extrabold tracking-tight">{e.title}</h2>
        <div className="mt-2 text-sm text-tx2">{e.venue?.name} · {e.startDate}–{e.endDate}</div>
      </div>
    </Link>
  );
}
```

- [ ] **Step 4: Run it green**

Run (in `web/`): `npx vitest run src/components/FeaturedCarousel.test.tsx` → PASS.

- [ ] **Step 5: Commit**

```bash
git add web/src/components/FeaturedCarousel.tsx web/src/components/FeaturedCarousel.test.tsx
git commit -m "feat(web): FeaturedCarousel (1.4s auto-advance, random master slides)"
```

---

## Task 17: Wire the carousel into the home page

Replace the single featured hero in `web/src/app/page.tsx` with `<FeaturedCarousel>`.

**Files:**
- Modify: `web/src/app/page.tsx`

- [ ] **Step 1: Load masters and render the carousel**

In `web/src/app/page.tsx`:

1. Add imports near the top:

```tsx
import { FeaturedCarousel } from "@/components/FeaturedCarousel";
import { parseMasters, type Master } from "@/lib/masters";
import mastersRaw from "../../public/data/masters.json";
```

2. Inside `Home()`, after `const catalog = loadCatalogSync();`, add:

```tsx
  const masters: Master[] = parseMasters(mastersRaw).masters;
```

3. Replace the existing featured block:

```tsx
          {featured && (
            <section className="mb-9 grid overflow-hidden rounded border border-line md:grid-cols-[1.1fr_0.9fr]">
              <div className="relative min-h-[320px]">
                <ExhibitionCardHero e={featured} />
              </div>
            </section>
          )}
```

with:

```tsx
          <FeaturedCarousel
            exhibitions={featured ? [featured] : []}
            masters={masters}
          />
```

4. Remove the now-unused `ExhibitionCardHero` function and its `PosterImage`/`Link` usages if
they become unused (lint will flag unused imports — keep `Link`/`PosterImage` only if still
referenced elsewhere in the file; they are used by `Section`/other code, so verify with lint
rather than deleting blindly).

- [ ] **Step 2: Verify build + lint + existing tests**

Run (in `web/`):
```bash
npm run lint
npx vitest run
```
Both green. If `masters.json` doesn't exist yet (Task 11 not run), create a minimal
placeholder so the import resolves: `echo '{"generated_at":"","masters":[]}' > web/public/data/masters.json` — the carousel then just shows the exhibition slide. (Replace it with the real file from Task 11.)

- [ ] **Step 3: Commit**

```bash
git add web/src/app/page.tsx
git commit -m "feat(web): use FeaturedCarousel as the home hero"
```

---

## Task 18: Masters list page (`/masters`)

**Files:**
- Create: `web/src/app/masters/page.tsx`

- [ ] **Step 1: Implement the list page**

Create `web/src/app/masters/page.tsx`:

```tsx
"use client";
import Link from "next/link";
import { useMemo } from "react";
import { PosterImage } from "@/components/PosterImage";
import { useLang } from "@/components/LanguageProvider";
import { inLocale } from "@/lib/catalog";
import { parseMasters, masterFaceImage, type Master, type Region } from "@/lib/masters";
import mastersRaw from "../../../public/data/masters.json";

const REGION_ORDER: Region[] = ["kr", "jp", "foreign"];
const REGION_KEY: Record<Region, string> = {
  kr: "masters.regionKr", jp: "masters.regionJp", foreign: "masters.regionForeign",
};

export default function MastersPage() {
  const { t, locale } = useLang();
  const masters = useMemo(() => parseMasters(mastersRaw).masters, []);
  const byRegion = (r: Region) => masters.filter((m) => m.region === r);

  return (
    <main className="mx-auto max-w-[1180px] px-7 py-10">
      <h1 className="text-[32px] font-extrabold tracking-tight">{t("masters.title")}</h1>
      <p className="mt-2 text-sm text-tx2">{t("masters.subtitle")}</p>

      {REGION_ORDER.map((r) => {
        const items = byRegion(r);
        if (items.length === 0) return null;
        return (
          <section key={r} className="pt-9">
            <h2 className="mb-4 text-lg font-bold tracking-tight">{t(REGION_KEY[r])}</h2>
            <div className="grid grid-cols-2 gap-4 md:grid-cols-4">
              {items.map((m) => <MasterCard key={m.id} m={m} locale={locale} t={t} />)}
            </div>
          </section>
        );
      })}
    </main>
  );
}

function MasterCard({ m, locale, t }: { m: Master; locale: any; t: (k: string, v?: any) => string }) {
  const name = inLocale(m.name, m.tr, locale, "name");
  const tagline = inLocale(m.tagline, m.tr, locale, "tagline");
  const years = m.birthYear ? t("masters.years", { birth: m.birthYear, death: m.deathYear ?? "" }) : "";
  return (
    <Link href={`/masters/${m.id}`} className="group block overflow-hidden rounded border border-line">
      <div className="relative aspect-[3/4]">
        <PosterImage src={masterFaceImage(m)} alt={name} />
      </div>
      <div className="p-3">
        <div className="font-semibold tracking-tight">{name}</div>
        {years && <div className="text-[12px] text-tx3">{years}</div>}
        {tagline && <div className="mt-1 line-clamp-2 text-[13px] text-tx2">{tagline}</div>}
      </div>
    </Link>
  );
}
```

NOTE: confirm `useLang()` exposes `locale` (the home page reads `t` only). Check
`web/src/components/LanguageProvider.tsx` — if the current locale is exposed under a
different name (e.g. `lang`), use that. If no locale is exposed, add it to the provider's
context value (it already holds the locale internally to drive `t`).

- [ ] **Step 2: Verify + commit**

Run (in `web/`): `npm run lint` then `npm run build` (or `npx next build`) → succeeds.

```bash
git add web/src/app/masters/page.tsx
git commit -m "feat(web): /masters list page grouped by region"
```

---

## Task 19: Master detail page (`/masters/[id]`)

**Files:**
- Create: `web/src/app/masters/[id]/page.tsx`

- [ ] **Step 1: Implement the detail page**

This app statically exports (GitHub Pages), so a dynamic route needs
`generateStaticParams`. Check an existing dynamic route — `web/src/app/exhibitions/[id]/page.tsx`
— and mirror exactly how it declares params and reads the route param (client vs server
component, `generateStaticParams` signature, how it gets `id`). Create
`web/src/app/masters/[id]/page.tsx` following that same pattern, rendering:

```tsx
"use client";
import { use, useMemo } from "react";
import Link from "next/link";
import { PosterImage } from "@/components/PosterImage";
import { useLang } from "@/components/LanguageProvider";
import { inLocale } from "@/lib/catalog";
import { parseMasters, type Master, type MasterWork } from "@/lib/masters";
import mastersRaw from "../../../../public/data/masters.json";

// Mirror generateStaticParams from app/exhibitions/[id]/page.tsx:
export function generateStaticParams() {
  return parseMasters(mastersRaw).masters.map((m) => ({ id: m.id }));
}

export default function MasterDetail({ params }: { params: Promise<{ id: string }> }) {
  // Match how exhibitions/[id] unwraps params (this app's Next version). If that
  // file uses `use(params)`, keep this; if it destructures directly, match it.
  const { id } = use(params);
  const { t, locale } = useLang();
  const master = useMemo(
    () => parseMasters(mastersRaw).masters.find((m) => m.id === id) ?? null,
    [id],
  );
  if (!master) {
    return <main className="mx-auto max-w-[900px] px-7 py-16 text-tx2">{t("common.loading")}</main>;
  }
  const name = inLocale(master.name, master.tr, locale, "name");
  const bio = inLocale(master.bio, master.tr, locale, "bio");
  const years = master.birthYear ? t("masters.years", { birth: master.birthYear, death: master.deathYear ?? "" }) : "";

  return (
    <main className="mx-auto max-w-[900px] px-7 py-10">
      <Link href="/masters" className="text-sm text-tx3 hover:text-tx">← {t("masters.title")}</Link>
      <header className="mt-4 flex items-center gap-4">
        {master.portraitUrl && (
          // eslint-disable-next-line @next/next/no-img-element
          <img src={master.portraitUrl} alt={name}
            className="h-16 w-16 rounded-full object-cover ring-1 ring-line" />
        )}
        <div>
          <h1 className="text-[28px] font-extrabold tracking-tight">{name}</h1>
          <div className="text-sm text-tx3">{years}{master.nationality ? ` · ${master.nationality}` : ""}</div>
        </div>
      </header>
      {bio && <p className="mt-4 text-[15px] leading-relaxed text-tx2">{bio}</p>}

      <div className="mt-10 space-y-12">
        {master.works.map((w) => <WorkBlock key={w.id} w={w} locale={locale} t={t} />)}
      </div>
    </main>
  );
}

function WorkBlock({ w, locale, t }: { w: MasterWork; locale: any; t: (k: string) => string }) {
  const title = inLocale(w.title, w.tr, locale, "title");
  const commentary = inLocale(w.commentary, w.tr, locale, "commentary");
  return (
    <article>
      <a href={w.sourceUrl ?? "#"} target="_blank" rel="noreferrer"
        className="relative block w-full overflow-hidden rounded bg-black/30">
        <PosterImage src={w.imageUrl} alt={title} />
      </a>
      <div className="mt-3">
        <div className="font-semibold tracking-tight">{title}</div>
        <div className="text-[13px] text-tx3">
          {[w.year, w.medium].filter(Boolean).join(" · ")}
        </div>
        {commentary && (
          <p className="mt-2 text-[14px] leading-relaxed text-tx2">{commentary}</p>
        )}
        <div className="mt-2 text-[12px] text-tx3">
          {t("masters.source")}: {w.credit}{" · "}
          {w.sourceUrl && (
            <a href={w.sourceUrl} target="_blank" rel="noreferrer" className="underline hover:text-tx">
              {t("masters.viewOriginal")}
            </a>
          )}
        </div>
      </div>
    </article>
  );
}
```

IMPORTANT: `PosterImage` may render a fixed aspect via absolute positioning (it's used inside
`relative` containers elsewhere). Check `web/src/components/PosterImage.tsx`; if it requires a
sized `relative` parent, wrap the work image in `<div className="relative aspect-[4/3]">…</div>`
like the list card does, instead of a bare anchor.

- [ ] **Step 2: Verify + commit**

Run (in `web/`): `npm run lint` then `npm run build` → succeeds (static params generated for
each master id).

```bash
git add web/src/app/masters/
git commit -m "feat(web): /masters/[id] detail page with works gallery + commentary"
```

---

## Task 20: Final verification

- [ ] **Step 1: Full Python suite**

Run: `ruff check src/ tests/` and `pytest -q` → all green.

- [ ] **Step 2: Full web suite + build**

Run (in `web/`): `npm run lint`, `npx vitest run`, `npm run build` → all green; static export
includes `/masters` and `/masters/[id]` pages.

- [ ] **Step 3: Manual smoke (optional, local)**

Run (in `web/`): `npm run dev`, open `/`, confirm the hero carousel auto-advances ~every 1.4s
and shows master slides (face + name) mixed with the featured exhibition; click a master slide
→ lands on `/masters/[id]`; `/masters` groups masters by 한국/일본/해외.

- [ ] **Step 4: Confirm nothing in the exhibitions pipeline changed**

Run: `git diff --stat main -- src/crawler/sources src/crawler/sinks src/crawler/normalize` →
empty (no edits to the live exhibitions pipeline).

---

## Self-review notes (author)

- **Spec coverage:** §5 data model → Tasks 1,8,13. §6 pipeline → Tasks 1–10. §7.1 carousel →
  Tasks 15,16,17. §7.2 list → Task 18. §7.3 detail → Task 19. §7.4 lib → Task 13. §7.5 i18n →
  Task 14. §8 workflow → Task 12. §9 testing → tests in each task. §3 commentary (ko gen +
  en/ja translate, cached, shipped) → Tasks 5,6,7,11. Roster scale §6 → Task 9.
- **Known reconciliation points (flagged inline, expected during execution):** museum fixture
  field reconciliation (Tasks 2,3); `web/src/test/lang.tsx` provider export name (Task 16);
  `useLang()` locale field name (Tasks 18,19); `PosterImage` sizing parent (Task 19);
  `exhibitions/[id]` dynamic-route + `generateStaticParams` pattern (Task 19); `crawl.yml`
  python-setup matching (Task 12). These are "match the existing pattern" checks, not
  placeholders.
- **Type consistency:** `RawWork`, `MasterSeed`, `SourceQuery`, `LocalizedText` (with tagline
  fields added in Task 8), `CommentaryWriter.master_text/work_text`, `Master`/`MasterWork`,
  `CarouselSlide` used consistently across tasks.
