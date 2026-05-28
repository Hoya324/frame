# 한국 사진 갤러리 7곳 소스 추가 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add 7 new Korean photography gallery source extractors (Goeun, Gallery Lux, Gallery Kong, Ryugaheon, Ilwoo Space, Sangsangmadang, Canon) following the existing `museum_hanmi` / `photo_sema` extractor pattern. No infra changes, single PR.

**Architecture:** Each site is one module `src/crawler/sources/<slug>.py` implementing the `SourceExtractor` protocol — class with `name: SourceName` and `crawl() -> Iterable[RawExhibition]`. Each module captures venue facts as module constants, fetches list pages with `httpx`, parses with `selectolax`, and emits `RawExhibition(source, source_url, raw=dict)`. Sangsangmadang adds a photo-category URL filter (whitelist) at the fetch step.

**Tech Stack:** Python 3.13, `httpx`, `selectolax` (HTML parsing), `tenacity` (retry), `respx` (test mocks), `pytest`.

**Spec:** [docs/superpowers/specs/2026-05-28-photo-sources-korea-expansion-design.md](../specs/2026-05-28-photo-sources-korea-expansion-design.md)

---

## File Structure

**Modify:**
- `src/crawler/models.py` — extend `SourceName` enum with 7 new entries
- `src/crawler/sources/__init__.py` — register 7 new modules

**Create (7 source modules):**
- `src/crawler/sources/goeun.py`
- `src/crawler/sources/gallery_lux.py`
- `src/crawler/sources/gallery_kong.py`
- `src/crawler/sources/ryugaheon.py`
- `src/crawler/sources/ilwoo_space.py`
- `src/crawler/sources/sangsangmadang.py`
- `src/crawler/sources/canon_gallery.py`

**Create (7 test files + 7 fixture dirs):**
- `tests/sources/test_goeun.py`, `tests/fixtures/goeun/`
- `tests/sources/test_gallery_lux.py`, `tests/fixtures/gallery_lux/`
- `tests/sources/test_gallery_kong.py`, `tests/fixtures/gallery_kong/`
- `tests/sources/test_ryugaheon.py`, `tests/fixtures/ryugaheon/`
- `tests/sources/test_ilwoo_space.py`, `tests/fixtures/ilwoo_space/`
- `tests/sources/test_sangsangmadang.py`, `tests/fixtures/sangsangmadang/`
- `tests/sources/test_canon_gallery.py`, `tests/fixtures/canon_gallery/`

**Create (integration):**
- `tests/integration/test_pipeline_korea_galleries.py` — one combined smoke test exercising all 7 sources through normalize+resolver+fake-sink

---

## Conventions (read once, all per-site tasks rely on these)

### `raw` dict keys that the existing normalizer reads

(verified by reading `src/crawler/normalize/normalize.py` 2026-05-28)

| Key | Type | Notes |
|---|---|---|
| `title` (required) | str | Title (Korean preferred, EN allowed) |
| `title_en` | str | optional English title |
| `description` | str | optional body text |
| `category` | str | feeds `medium` classification keywords |
| `poster_image_url` | str | absolute URL |
| `date_range` | str | raw text like `2026.05.22. 금 ~ 2026.09.30. 수` — `parse_date_range` handles many formats |
| `exhibition_type_text` | str | maps to `ExhibitionType` |
| `fee_text` | str | maps to `FeeType` |
| `price_min` / `price_max` | int | numeric |
| `price_breakdown` | list of `{label, amount}` dicts | artmap pattern |
| `price_notes` | str | discount notes |
| `open_hours` | str | raw text |
| `genre_tags` | list[str] | |
| `activities` | list[str] | |
| `artists` | list[str] | raw artist names |
| `venue_name` | str | matches against `_overrides`/`Venues` |
| `venue_region` | str | e.g. "서울" / "부산" |
| `venue_address` | str | raw address |
| `organizer` | str | organizer name |

Any unknown key is silently ignored. Stick to these.

### Module skeleton (reference — see Task 2 for filled-in version)

Every site module follows this layout:

```python
"""<Site display name> (<domain>) — exhibition list extractor.

Strategy: ...
Verified <YYYY-MM-DD>.
"""

from __future__ import annotations

import time
from collections.abc import Iterable

import httpx
from selectolax.parser import HTMLParser
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

from crawler.models import RawExhibition, SourceName
from crawler.sources.base import register_source

_BASE_URL = "https://..."
_LIST_URL = f"{_BASE_URL}/..."
_USER_AGENT = "PhotoExhibitionCrawler/0.1 (+contact@example.com)"

# Fixed venue facts for this single-venue gallery.
_VENUE_NAME = "..."
_VENUE_REGION = "..."           # 시/도
_VENUE_ADDRESS = "..."          # 거리 주소
_VENUE_WEBSITE = _BASE_URL


class <SiteName>Extractor:
    name = SourceName.<ENUM_NAME>

    def __init__(self, delay_s: float = 1.0, timeout_s: float = 20.0) -> None:
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
    def _get(self, url: str) -> str:
        r = self._client.get(url)
        r.raise_for_status()
        return r.text

    def crawl(self) -> Iterable[RawExhibition]:
        html = self._get(_LIST_URL)
        for card in _extract_cards(html):
            yield RawExhibition(
                source=SourceName.<ENUM_NAME>,
                source_url=card["source_url"],
                raw={k: v for k, v in card.items() if k != "source_url"},
            )


def _extract_cards(html: str) -> list[dict]:
    """Parse the list page into card dicts (one per exhibition)."""
    doc = HTMLParser(html)
    cards: list[dict] = []
    for el in doc.css("..."):  # site-specific
        # ... extract title, date_range, poster_image_url, source_url ...
        cards.append({
            "source_url": "...",
            "title": "...",
            "venue_name": _VENUE_NAME,
            "venue_region": _VENUE_REGION,
            "venue_address": _VENUE_ADDRESS,
            "date_range": "...",
            "poster_image_url": "...",
        })
    return cards


register_source(SourceName.<ENUM_NAME>, <SiteName>Extractor)
```

### Test skeleton

```python
import json
from pathlib import Path

import httpx
import respx

from crawler.models import SourceName
from crawler.sources.<slug> import <SiteName>Extractor

FIXTURE_DIR = Path(__file__).parent.parent / "fixtures" / "<slug>"

_LIST_URL = "https://.../..."


def _load_fixture(name: str) -> str:
    return (FIXTURE_DIR / name).read_text(encoding="utf-8")


def _load_expected() -> list[dict]:
    return [
        json.loads(line)
        for line in (FIXTURE_DIR / "expected.jsonl").read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


@respx.mock
def test_<slug>_extractor_parses_cards():
    respx.get(_LIST_URL).mock(return_value=httpx.Response(200, text=_load_fixture("list_page_1.html")))

    raws = list(<SiteName>Extractor(delay_s=0.0).crawl())
    assert len(raws) >= 1
    assert all(r.source is SourceName.<ENUM_NAME> for r in raws)

    by_url = {str(r.source_url): r for r in raws}
    for exp in _load_expected():
        actual = by_url.get(exp["source_url"])
        assert actual is not None, f"missing card for {exp['source_url']!r}"
        for k, v in exp["raw"].items():
            assert actual.raw.get(k) == v, f"mismatch on {exp['source_url']} field {k!r}: got {actual.raw.get(k)!r}, expected {v!r}"


@respx.mock
def test_<slug>_extractor_empty_page_returns_nothing():
    respx.get(_LIST_URL).mock(return_value=httpx.Response(200, text="<html><body></body></html>"))
    raws = list(<SiteName>Extractor(delay_s=0.0).crawl())
    assert raws == []
```

### Fixture `expected.jsonl` format

One JSON object per line. Each object has `source_url` and `raw` (subset of expected raw keys — test only checks listed keys, missing keys are not asserted). Example:

```jsonl
{"source_url": "https://www.example.com/exhibition/1", "raw": {"title": "...", "venue_name": "...", "date_range": "...", "poster_image_url": "https://..."}}
```

---

## Task 1: Extend `SourceName` enum with 7 new entries

**Files:**
- Modify: `src/crawler/models.py:11-17`

- [ ] **Step 1: Modify enum**

Replace the `SourceName` block at `src/crawler/models.py:11-17` with:

```python
class SourceName(StrEnum):
    ARTMAP = "artmap"
    NAVER = "naver"
    PHOTO_SEMA = "photo_sema"
    MUSEUM_HANMI = "museum_hanmi"
    KOBA = "koba"
    GOEUN = "goeun"
    GALLERY_LUX = "gallery_lux"
    GALLERY_KONG = "gallery_kong"
    RYUGAHEON = "ryugaheon"
    ILWOO_SPACE = "ilwoo_space"
    SANGSANGMADANG = "sangsangmadang"
    CANON_GALLERY = "canon_gallery"
```

- [ ] **Step 2: Run existing tests to confirm enum change doesn't break anything**

```bash
.venv/bin/pytest -q
```

Expected: 217 pass (enum addition is backward-compatible).

- [ ] **Step 3: Commit**

```bash
git add src/crawler/models.py
git commit -m "feat(models): add 7 SourceName entries for Korea gallery expansion"
```

---

## Task 2: `goeun` (고은사진미술관) — full recipe, used as template by Tasks 3-8

**Site facts:**
- Slug: `goeun`
- SourceName: `SourceName.GOEUN` ("goeun")
- Domain: `https://www.goeunmuseum.org`
- Pages: 분리형 — `/exhibition/current` (진행중) + `/exhibition/upcoming` (예정). Both must be crawled. Skip `/exhibition/past`.
- Venue: 고은사진미술관 / 부산 / 부산광역시 해운대구

**Files:**
- Create: `src/crawler/sources/goeun.py`
- Create: `tests/sources/test_goeun.py`
- Create: `tests/fixtures/goeun/list_current.html`
- Create: `tests/fixtures/goeun/list_upcoming.html`
- Create: `tests/fixtures/goeun/expected.jsonl`

- [ ] **Step 1: Verify URL is alive and static, capture HTML**

Run inside the worktree:

```bash
.venv/bin/python -c "import httpx; r = httpx.get('https://www.goeunmuseum.org/exhibition/current', timeout=20, follow_redirects=True, headers={'User-Agent':'Mozilla/5.0'}); print(r.status_code); print(r.text[:2000])"
.venv/bin/python -c "import httpx; r = httpx.get('https://www.goeunmuseum.org/exhibition/upcoming', timeout=20, follow_redirects=True, headers={'User-Agent':'Mozilla/5.0'}); print(r.status_code); print(r.text[:2000])"
```

Expected: status 200 and HTML body with exhibition cards in the first 2 KB. If status ≠ 200 or content is empty / JS-only, STOP and escalate — do not proceed. Document the issue in the commit message and skip this site (note in PR description).

If URL pattern differs (site redesigned), inspect `https://www.goeunmuseum.org/` first to find the actual exhibition section URL and update the constants below.

- [ ] **Step 2: Save raw HTML as fixtures**

```bash
mkdir -p tests/fixtures/goeun
.venv/bin/python -c "
import httpx
for slug, url in [('list_current', 'https://www.goeunmuseum.org/exhibition/current'),
                  ('list_upcoming', 'https://www.goeunmuseum.org/exhibition/upcoming')]:
    r = httpx.get(url, timeout=20, follow_redirects=True, headers={'User-Agent':'Mozilla/5.0'})
    open(f'tests/fixtures/goeun/{slug}.html','w',encoding='utf-8').write(r.text)
    print(slug, len(r.text))
"
```

Expected: two files written, each at least 5000 chars.

- [ ] **Step 3: Inspect HTML and identify card selector**

Open `tests/fixtures/goeun/list_current.html` and find one exhibition card. Identify:
- Card outer selector (e.g. `div.exhibition-item`, `li.list-item`)
- Title selector within card
- Date range selector within card
- Poster image selector within card
- Detail page URL selector within card (usually `a[href]`)

Write these CSS selectors down — they go into `_extract_cards()` in step 6.

If the page has no static exhibition content (only JS placeholder), STOP — the site needs Playwright fallback which is out of this plan's scope. Document and skip.

- [ ] **Step 4: Build `expected.jsonl` from observed cards**

For each visible exhibition card in the current+upcoming fixtures (typically 1–4 entries total), write one JSON line. Include only the **stable** fields you can verify by eye:

```jsonl
{"source_url": "https://www.goeunmuseum.org/exhibition/...", "raw": {"title": "...", "venue_name": "고은사진미술관", "venue_region": "부산", "date_range": "..."}}
```

Use absolute URLs in `source_url`. The test only asserts that listed keys match — it doesn't require every raw key, so omit fragile ones (e.g. relative poster paths).

- [ ] **Step 5: Write the failing test at `tests/sources/test_goeun.py`**

```python
import json
from pathlib import Path

import httpx
import respx

from crawler.models import SourceName
from crawler.sources.goeun import GoeunExtractor

FIXTURE_DIR = Path(__file__).parent.parent / "fixtures" / "goeun"

_CURRENT_URL = "https://www.goeunmuseum.org/exhibition/current"
_UPCOMING_URL = "https://www.goeunmuseum.org/exhibition/upcoming"


def _load_fixture(name: str) -> str:
    return (FIXTURE_DIR / name).read_text(encoding="utf-8")


def _load_expected() -> list[dict]:
    return [
        json.loads(line)
        for line in (FIXTURE_DIR / "expected.jsonl").read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


@respx.mock
def test_goeun_extractor_parses_both_pages():
    respx.get(_CURRENT_URL).mock(return_value=httpx.Response(200, text=_load_fixture("list_current.html")))
    respx.get(_UPCOMING_URL).mock(return_value=httpx.Response(200, text=_load_fixture("list_upcoming.html")))

    raws = list(GoeunExtractor(delay_s=0.0).crawl())
    assert len(raws) >= 1, f"expected at least 1 exhibition, got {len(raws)}"
    assert all(r.source is SourceName.GOEUN for r in raws)

    by_url = {str(r.source_url): r for r in raws}
    for exp in _load_expected():
        actual = by_url.get(exp["source_url"])
        assert actual is not None, f"missing card for {exp['source_url']!r}"
        for k, v in exp["raw"].items():
            assert actual.raw.get(k) == v, (
                f"mismatch on {exp['source_url']} field {k!r}: "
                f"got {actual.raw.get(k)!r}, expected {v!r}"
            )


@respx.mock
def test_goeun_extractor_empty_pages_yield_nothing():
    empty = "<html><body></body></html>"
    respx.get(_CURRENT_URL).mock(return_value=httpx.Response(200, text=empty))
    respx.get(_UPCOMING_URL).mock(return_value=httpx.Response(200, text=empty))
    raws = list(GoeunExtractor(delay_s=0.0).crawl())
    assert raws == []
```

- [ ] **Step 6: Run test — confirm FAIL**

```bash
.venv/bin/pytest tests/sources/test_goeun.py -v
```

Expected: ModuleNotFoundError or ImportError for `crawler.sources.goeun`.

- [ ] **Step 7: Implement module at `src/crawler/sources/goeun.py`**

Replace the four `?` placeholders in the parser (item / title / date / link selectors) with the ones identified in step 3. Replace `?ABSOLUTE_OR_REL?` with absolute-URL handling (`urljoin(_BASE_URL, href)` if relative).

```python
"""고은사진미술관 (Goeun Museum of Photography, goeunmuseum.org) — list extractor.

Strategy: GET /exhibition/current and /exhibition/upcoming. Parse static
WordPress / CMS HTML cards. Skip /past.
Verified 2026-05-28.
"""

from __future__ import annotations

import time
from collections.abc import Iterable
from urllib.parse import urljoin

import httpx
from selectolax.parser import HTMLParser
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

from crawler.models import RawExhibition, SourceName
from crawler.sources.base import register_source

_BASE_URL = "https://www.goeunmuseum.org"
_LIST_URLS = (
    f"{_BASE_URL}/exhibition/current",
    f"{_BASE_URL}/exhibition/upcoming",
)
_USER_AGENT = "PhotoExhibitionCrawler/0.1 (+contact@example.com)"

_VENUE_NAME = "고은사진미술관"
_VENUE_REGION = "부산"
_VENUE_ADDRESS = "부산광역시 해운대구"  # refine if site exposes street address


class GoeunExtractor:
    name = SourceName.GOEUN

    def __init__(self, delay_s: float = 1.0, timeout_s: float = 20.0) -> None:
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
    def _get(self, url: str) -> str:
        r = self._client.get(url)
        r.raise_for_status()
        return r.text

    def crawl(self) -> Iterable[RawExhibition]:
        seen: set[str] = set()
        for url in _LIST_URLS:
            html = self._get(url)
            for card in _extract_cards(html):
                if card["source_url"] in seen:
                    continue
                seen.add(card["source_url"])
                yield RawExhibition(
                    source=SourceName.GOEUN,
                    source_url=card["source_url"],
                    raw={k: v for k, v in card.items() if k != "source_url"},
                )
            if self.delay_s > 0:
                time.sleep(self.delay_s)


def _extract_cards(html: str) -> list[dict]:
    doc = HTMLParser(html)
    cards: list[dict] = []
    for item in doc.css("?ITEM_SELECTOR?"):
        link = item.css_first("a[href]")
        href = link.attributes.get("href") if link else None
        if not href:
            continue
        url = urljoin(_BASE_URL, href)

        title_el = item.css_first("?TITLE_SELECTOR?")
        title = title_el.text(strip=True) if title_el else ""
        if not title:
            continue

        date_el = item.css_first("?DATE_SELECTOR?")
        date_range = date_el.text(strip=True) if date_el else None

        img = item.css_first("img")
        poster = img.attributes.get("src") if img else None
        if poster:
            poster = urljoin(_BASE_URL, poster)

        cards.append({
            "source_url": url,
            "title": title,
            "venue_name": _VENUE_NAME,
            "venue_region": _VENUE_REGION,
            "venue_address": _VENUE_ADDRESS,
            "date_range": date_range,
            "poster_image_url": poster,
        })
    return cards


register_source(SourceName.GOEUN, GoeunExtractor)
```

- [ ] **Step 8: Run test — confirm PASS**

```bash
.venv/bin/pytest tests/sources/test_goeun.py -v
```

Expected: 2 passed. If the parse asserts fail, the `?...?` selectors are wrong — re-inspect the fixture and adjust.

- [ ] **Step 9: Lint**

```bash
.venv/bin/ruff check src/crawler/sources/goeun.py tests/sources/test_goeun.py
```

Expected: no issues.

- [ ] **Step 10: Commit**

```bash
git add src/crawler/sources/goeun.py tests/sources/test_goeun.py tests/fixtures/goeun/
git commit -m "feat(sources): add goeun (고은사진미술관) extractor"
```

---

## Task 3: `gallery_lux` (갤러리 룩스)

**Site facts:**
- Slug: `gallery_lux`
- SourceName: `SourceName.GALLERY_LUX` ("gallery_lux")
- Domain (best known): `https://www.gallerylux.net` (verify in step 1; fallback try `gallerylux.kr`)
- Page pattern: 단순형 — single exhibition listing page expected at `/exhibition` or `/exhibitions`
- Venue: 갤러리 룩스 / 서울 / 서울특별시 종로구 (verify in step 3 from page footer/contact)

**Files:**
- Create: `src/crawler/sources/gallery_lux.py`
- Create: `tests/sources/test_gallery_lux.py`
- Create: `tests/fixtures/gallery_lux/list_page_1.html`
- Create: `tests/fixtures/gallery_lux/expected.jsonl`

- [ ] **Step 1: Verify domain and exhibition list URL**

```bash
for u in https://www.gallerylux.net/ https://www.gallerylux.net/exhibition https://www.gallerylux.net/exhibitions https://www.gallerylux.kr/ ; do
  echo "=== $u ==="
  .venv/bin/python -c "import httpx, sys; r = httpx.get(sys.argv[1], timeout=15, follow_redirects=True, headers={'User-Agent':'Mozilla/5.0'}); print(r.status_code, str(r.url)[:80])" "$u" 2>&1 || true
done
```

Pick the first URL that returns 200 with HTML containing exhibition listings. If none works, STOP and escalate.

- [ ] **Step 2: Capture list page**

```bash
mkdir -p tests/fixtures/gallery_lux
.venv/bin/python -c "
import httpx, sys
url = sys.argv[1]
r = httpx.get(url, timeout=20, follow_redirects=True, headers={'User-Agent':'Mozilla/5.0'})
open('tests/fixtures/gallery_lux/list_page_1.html','w',encoding='utf-8').write(r.text)
print(len(r.text))
" "<URL FROM STEP 1>"
```

- [ ] **Step 3: Identify selectors and venue address**

Open the fixture. Record:
- Card outer selector
- Title / date / poster / detail-link selectors
- Footer/contact venue address (set `_VENUE_ADDRESS` to this exact string)

- [ ] **Step 4: Write `expected.jsonl`**

Same format as Task 2 step 4. 1–3 entries.

- [ ] **Step 5: Write the failing test at `tests/sources/test_gallery_lux.py`**

Adapt Task 2 step 5 verbatim with these substitutions: `goeun` → `gallery_lux`, `GoeunExtractor` → `GalleryLuxExtractor`, `SourceName.GOEUN` → `SourceName.GALLERY_LUX`, fixture URL constants → the single `_LIST_URL` from step 1. Remove the `_UPCOMING_URL` mock and the second-page logic — this is a single-page site. The first test name becomes `test_gallery_lux_extractor_parses_cards`, the empty test becomes `test_gallery_lux_extractor_empty_page_yields_nothing`.

- [ ] **Step 6: Run test — confirm FAIL**

```bash
.venv/bin/pytest tests/sources/test_gallery_lux.py -v
```

- [ ] **Step 7: Implement module at `src/crawler/sources/gallery_lux.py`**

Use the museum_hanmi-style skeleton from the Conventions section. Single-page `crawl()`:

```python
def crawl(self) -> Iterable[RawExhibition]:
    html = self._get(_LIST_URL)
    for card in _extract_cards(html):
        yield RawExhibition(
            source=SourceName.GALLERY_LUX,
            source_url=card["source_url"],
            raw={k: v for k, v in card.items() if k != "source_url"},
        )
```

Fill `_VENUE_NAME = "갤러리 룩스"`, `_VENUE_REGION = "서울"`, `_VENUE_ADDRESS` from step 3, `_BASE_URL` and `_LIST_URL` from step 1.

Implement `_extract_cards()` using the selectors from step 3, following the goeun parser structure (urljoin for relative hrefs, skip cards with empty title).

End with:

```python
register_source(SourceName.GALLERY_LUX, GalleryLuxExtractor)
```

- [ ] **Step 8: Run test — confirm PASS**

```bash
.venv/bin/pytest tests/sources/test_gallery_lux.py -v
```

- [ ] **Step 9: Lint**

```bash
.venv/bin/ruff check src/crawler/sources/gallery_lux.py tests/sources/test_gallery_lux.py
```

- [ ] **Step 10: Commit**

```bash
git add src/crawler/sources/gallery_lux.py tests/sources/test_gallery_lux.py tests/fixtures/gallery_lux/
git commit -m "feat(sources): add gallery_lux (갤러리 룩스) extractor"
```

---

## Task 4: `gallery_kong` (공근혜갤러리)

**Site facts:**
- Slug: `gallery_kong`
- SourceName: `SourceName.GALLERY_KONG` ("gallery_kong")
- Domain (best known): `https://www.gallerykong.com`
- Page pattern: 단순형 — exhibitions list at `/exhibitions/current` or `/exhibition`
- Venue: 공근혜갤러리 / 서울 / 서울특별시 종로구 삼청로 (verify)

**Files:** Same shape as Task 3, with `gallery_kong` substituted.

- [ ] **Step 1: Verify domain and list URL** — same procedure as Task 3 step 1, with candidates `https://www.gallerykong.com/`, `/exhibitions`, `/exhibitions/current`, `/current`.

- [ ] **Step 2: Capture list page to `tests/fixtures/gallery_kong/list_page_1.html`** — same as Task 3 step 2.

- [ ] **Step 3: Identify selectors + venue address from page footer/contact** — same as Task 3 step 3.

- [ ] **Step 4: Write `expected.jsonl`** — same format.

- [ ] **Step 5: Write the failing test at `tests/sources/test_gallery_kong.py`** — adapt Task 3 step 5 with `gallery_lux` → `gallery_kong`, `GalleryLux` → `GalleryKong`, `GALLERY_LUX` → `GALLERY_KONG`.

- [ ] **Step 6: Run test, confirm FAIL.**

```bash
.venv/bin/pytest tests/sources/test_gallery_kong.py -v
```

- [ ] **Step 7: Implement `src/crawler/sources/gallery_kong.py`** — adapt the Task 3 module with name swaps and the selectors from step 3. `_VENUE_NAME = "공근혜갤러리"`, `_VENUE_REGION = "서울"`, `_VENUE_ADDRESS` from step 3.

- [ ] **Step 8: Run test, confirm PASS.**

- [ ] **Step 9: Lint.**

- [ ] **Step 10: Commit.**

```bash
git add src/crawler/sources/gallery_kong.py tests/sources/test_gallery_kong.py tests/fixtures/gallery_kong/
git commit -m "feat(sources): add gallery_kong (공근혜갤러리) extractor"
```

---

## Task 5: `ryugaheon` (류가헌)

**Site facts:**
- Slug: `ryugaheon`
- SourceName: `SourceName.RYUGAHEON` ("ryugaheon")
- Domain (best known): `https://www.ryugaheon.com`
- Page pattern: 단순형. The site has a 책방 menu — make sure to scrape only the 전시 page.
- Venue: 류가헌 / 서울 / 서울특별시 종로구 (verify)

**Files:** Same shape, `ryugaheon` substituted.

- [ ] **Step 1: Verify list URL.** Candidates: `https://www.ryugaheon.com/`, `/exhibition`, `/exhibitions`, `/전시`, `/현재전시`. Pick the one that returns 200 and HTML containing 전시 cards (not 책방/book cards).

- [ ] **Step 2: Capture list page → `tests/fixtures/ryugaheon/list_page_1.html`.**

- [ ] **Step 3: Identify selectors.** Crucially confirm the cards are exhibitions (not books) — if both share the same card class, narrow the selector to the exhibition section (look for parent `section` / `div` with exhibition-specific id/class).

- [ ] **Step 4: Write `expected.jsonl`.**

- [ ] **Step 5: Write the failing test at `tests/sources/test_ryugaheon.py`** — same template, swap names.

- [ ] **Step 6: Run test, confirm FAIL.**

- [ ] **Step 7: Implement `src/crawler/sources/ryugaheon.py`.** `_VENUE_NAME = "류가헌"`, `_VENUE_REGION = "서울"`, `_VENUE_ADDRESS` from step 3.

- [ ] **Step 8: Run test, confirm PASS.**

- [ ] **Step 9: Lint.**

- [ ] **Step 10: Commit.**

```bash
git add src/crawler/sources/ryugaheon.py tests/sources/test_ryugaheon.py tests/fixtures/ryugaheon/
git commit -m "feat(sources): add ryugaheon (류가헌) extractor"
```

---

## Task 6: `ilwoo_space` (일우스페이스)

**Site facts:**
- Slug: `ilwoo_space`
- SourceName: `SourceName.ILWOO_SPACE` ("ilwoo_space")
- Domain (best known): `https://www.ilwoospace.org`
- Page pattern: 단순형. 일우사진상 수상자 전시 중심.
- Venue: 일우스페이스 / 서울 / 서울특별시 중구 서소문로 117 대한항공빌딩 (verify)

**Files:** Same shape, `ilwoo_space` substituted.

- [ ] **Step 1: Verify list URL.** Candidates: `https://www.ilwoospace.org/`, `/exhibition`, `/exhibitions`, `https://www.ilwoo.org/`. Pick first 200-with-cards.

- [ ] **Step 2: Capture → `tests/fixtures/ilwoo_space/list_page_1.html`.**

- [ ] **Step 3: Identify selectors + venue address.**

- [ ] **Step 4: Write `expected.jsonl`.**

- [ ] **Step 5: Write the failing test at `tests/sources/test_ilwoo_space.py`** — same template, swap names.

- [ ] **Step 6: Run test, confirm FAIL.**

- [ ] **Step 7: Implement `src/crawler/sources/ilwoo_space.py`.** `_VENUE_NAME = "일우스페이스"`, `_VENUE_REGION = "서울"`, `_VENUE_ADDRESS` from step 3.

- [ ] **Step 8: Run test, confirm PASS.**

- [ ] **Step 9: Lint.**

- [ ] **Step 10: Commit.**

```bash
git add src/crawler/sources/ilwoo_space.py tests/sources/test_ilwoo_space.py tests/fixtures/ilwoo_space/
git commit -m "feat(sources): add ilwoo_space (일우스페이스) extractor"
```

---

## Task 7: `sangsangmadang` (KT&G 상상마당 갤러리) — special: photo whitelist

**Site facts:**
- Slug: `sangsangmadang`
- SourceName: `SourceName.SANGSANGMADANG` ("sangsangmadang")
- Domain (best known): `https://www.sangsangmadang.com`
- Page pattern: 분리형 + **mixed-media**. Sangsangmadang hosts photo, painting, illustration. We must only emit photo exhibitions.
- Venue: KT&G 상상마당 갤러리. Multiple branches (홍대, 논현, 부산, 춘천). Treat 홍대 갤러리 as the main scrape target. If page exposes branch in card, capture as `venue_name = f"KT&G 상상마당 {branch} 갤러리"`.

**Whitelist strategy (per spec §3, option A):**

The site exposes category filters in URL or page tabs. Identify in step 3 whether the photo category has a stable URL filter (e.g. `?category=photo` or `/exhibition?type=photography`). If yes, scrape ONLY that URL. If categorization is per-card (tag inside card HTML), filter post-fetch by tag containing `사진` or `photo`.

**Files:** Same shape, `sangsangmadang` substituted.

- [ ] **Step 1: Verify exhibition list URLs (both filter-by-URL and unfiltered).**

```bash
for u in https://www.sangsangmadang.com/exhibitionList https://www.sangsangmadang.com/exhibition https://www.sangsangmadang.com/gallery ; do
  echo "=== $u ==="
  .venv/bin/python -c "import httpx, sys; r = httpx.get(sys.argv[1], timeout=15, follow_redirects=True, headers={'User-Agent':'Mozilla/5.0'}); print(r.status_code, str(r.url)[:80])" "$u" 2>&1 || true
done
```

- [ ] **Step 2: Capture both photo-only and full list pages**

```bash
mkdir -p tests/fixtures/sangsangmadang
# Save the unfiltered list AND a category-filtered URL if found in step 1
```

Save the unfiltered listing as `list_all.html` and (if filter URL exists) `list_photo.html`. Also include at least one non-photo card in the unfiltered fixture so the test can verify it's filtered out.

- [ ] **Step 3: Identify category signal**

Inside `list_all.html`, find how a card declares its category. Typical patterns:
- `<span class="category">사진</span>` inside card
- `data-category="photo"` attribute on card outer
- Separate URL like `/exhibition?cat=photo`

Record which one applies. Branch handling: if a card shows 홍대/논현/부산/춘천, capture into `branch` variable.

- [ ] **Step 4: Write `expected.jsonl`**

Two entry kinds:
- At least 1 photo exhibition that MUST appear in output.
- At least 1 non-photo exhibition that MUST be absent. Encode the absent ones in a separate `unexpected.jsonl` file (one URL per line) so the test can assert exclusion.

Example `unexpected.jsonl`:

```
https://www.sangsangmadang.com/exhibition/12345
https://www.sangsangmadang.com/exhibition/12346
```

- [ ] **Step 5: Write the failing test at `tests/sources/test_sangsangmadang.py`**

```python
import json
from pathlib import Path

import httpx
import respx

from crawler.models import SourceName
from crawler.sources.sangsangmadang import SangsangmadangExtractor

FIXTURE_DIR = Path(__file__).parent.parent / "fixtures" / "sangsangmadang"

# Use the actual list URL identified in step 1
_LIST_URL = "<URL FROM STEP 1>"


def _load_fixture(name: str) -> str:
    return (FIXTURE_DIR / name).read_text(encoding="utf-8")


def _load_expected() -> list[dict]:
    return [
        json.loads(line)
        for line in (FIXTURE_DIR / "expected.jsonl").read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def _load_unexpected() -> list[str]:
    p = FIXTURE_DIR / "unexpected.jsonl"
    if not p.exists():
        return []
    return [line.strip() for line in p.read_text(encoding="utf-8").splitlines() if line.strip()]


@respx.mock
def test_sangsangmadang_extractor_emits_only_photo_exhibitions():
    respx.get(_LIST_URL).mock(return_value=httpx.Response(200, text=_load_fixture("list_all.html")))

    raws = list(SangsangmadangExtractor(delay_s=0.0).crawl())
    assert all(r.source is SourceName.SANGSANGMADANG for r in raws)

    urls = {str(r.source_url) for r in raws}

    for exp in _load_expected():
        assert exp["source_url"] in urls, f"expected photo exhibition missing: {exp['source_url']!r}"

    for forbidden in _load_unexpected():
        assert forbidden not in urls, f"non-photo exhibition leaked through: {forbidden!r}"

    by_url = {str(r.source_url): r for r in raws}
    for exp in _load_expected():
        for k, v in exp["raw"].items():
            assert by_url[exp["source_url"]].raw.get(k) == v, (
                f"mismatch on {exp['source_url']} field {k!r}"
            )


@respx.mock
def test_sangsangmadang_extractor_empty_page_yields_nothing():
    respx.get(_LIST_URL).mock(return_value=httpx.Response(200, text="<html><body></body></html>"))
    raws = list(SangsangmadangExtractor(delay_s=0.0).crawl())
    assert raws == []
```

- [ ] **Step 6: Run test, confirm FAIL.**

```bash
.venv/bin/pytest tests/sources/test_sangsangmadang.py -v
```

- [ ] **Step 7: Implement `src/crawler/sources/sangsangmadang.py` with photo whitelist**

Same skeleton as goeun. Filter logic in `_extract_cards()`:

```python
_PHOTO_KEYWORDS = ("사진", "포토", "photo", "Photo", "PHOTO")


def _is_photo_card(category_text: str | None) -> bool:
    if not category_text:
        return False
    return any(kw in category_text for kw in _PHOTO_KEYWORDS)


def _extract_cards(html: str) -> list[dict]:
    doc = HTMLParser(html)
    cards: list[dict] = []
    for item in doc.css("?CARD_SELECTOR?"):
        category_el = item.css_first("?CATEGORY_SELECTOR?")
        category_text = category_el.text(strip=True) if category_el else None
        if not _is_photo_card(category_text):
            continue
        # ... usual parsing ...
        cards.append({...})
    return cards
```

Set `_VENUE_NAME = "KT&G 상상마당 갤러리"`, `_VENUE_REGION = "서울"`, branch handling per step 3.

- [ ] **Step 8: Run test, confirm PASS.**

If a non-photo URL leaks, narrow `_is_photo_card`. If a photo URL is missing, widen `_PHOTO_KEYWORDS` or fix the selector.

- [ ] **Step 9: Lint.**

```bash
.venv/bin/ruff check src/crawler/sources/sangsangmadang.py tests/sources/test_sangsangmadang.py
```

- [ ] **Step 10: Commit.**

```bash
git add src/crawler/sources/sangsangmadang.py tests/sources/test_sangsangmadang.py tests/fixtures/sangsangmadang/
git commit -m "feat(sources): add sangsangmadang (KT&G 상상마당) extractor with photo whitelist"
```

---

## Task 8: `canon_gallery` (캐논 갤러리)

**Site facts:**
- Slug: `canon_gallery`
- SourceName: `SourceName.CANON_GALLERY` ("canon_gallery")
- Domain (best known): `https://www.canon-ci.co.kr` (Canon Korea consumer site, photo gallery section). Fallback candidates: `canon.co.kr`, `canon-camera.com/kr`.
- Page pattern: 단순형. 정기 공모전 수상작 전시 중심.
- Venue: 캐논 갤러리 / 서울 / 서울특별시 강남구 (verify; canon-ci runs gallery from headquarters)

**Files:** Same shape, `canon_gallery` substituted.

- [ ] **Step 1: Verify exhibition list URL.**

```bash
for u in https://www.canon-ci.co.kr/Gallery/CanonGallery.aspx https://www.canon-ci.co.kr/gallery https://www.canon.co.kr/gallery ; do
  echo "=== $u ==="
  .venv/bin/python -c "import httpx, sys; r = httpx.get(sys.argv[1], timeout=15, follow_redirects=True, headers={'User-Agent':'Mozilla/5.0'}); print(r.status_code, str(r.url)[:80])" "$u" 2>&1 || true
done
```

Canon's site has historically been ASP.NET-based, so URL may have `.aspx` extension and use form POSTs. If the site uses JavaScript paginated content, STOP and escalate — this is a Playwright fallback case.

- [ ] **Step 2: Capture → `tests/fixtures/canon_gallery/list_page_1.html`.**

- [ ] **Step 3: Identify selectors + venue address.**

- [ ] **Step 4: Write `expected.jsonl`.**

- [ ] **Step 5: Write the failing test at `tests/sources/test_canon_gallery.py`** — same template, swap names.

- [ ] **Step 6: Run test, confirm FAIL.**

- [ ] **Step 7: Implement `src/crawler/sources/canon_gallery.py`.** `_VENUE_NAME = "캐논 갤러리"`, `_VENUE_REGION = "서울"`, `_VENUE_ADDRESS` from step 3.

- [ ] **Step 8: Run test, confirm PASS.**

- [ ] **Step 9: Lint.**

- [ ] **Step 10: Commit.**

```bash
git add src/crawler/sources/canon_gallery.py tests/sources/test_canon_gallery.py tests/fixtures/canon_gallery/
git commit -m "feat(sources): add canon_gallery (캐논 갤러리) extractor"
```

---

## Task 9: Register all 7 new sources in `__init__.py`

**Files:**
- Modify: `src/crawler/sources/__init__.py:8-13`

- [ ] **Step 1: Update the import list**

Replace the existing import block:

```python
from crawler.sources import (
    artmap,  # noqa: F401
    canon_gallery,  # noqa: F401
    gallery_kong,  # noqa: F401
    gallery_lux,  # noqa: F401
    goeun,  # noqa: F401
    ilwoo_space,  # noqa: F401
    koba,  # noqa: F401
    museum_hanmi,  # noqa: F401
    photo_sema,  # noqa: F401
    ryugaheon,  # noqa: F401
    sangsangmadang,  # noqa: F401
)
```

Alphabetical order. Keep the trailing Naver blocked-comment block untouched.

- [ ] **Step 2: Verify registry**

```bash
.venv/bin/python -c "
from crawler.sources import base
import crawler.sources  # triggers registration
print(sorted(s.value for s in base.all_sources()))
"
```

Expected output:

```
['artmap', 'canon_gallery', 'gallery_kong', 'gallery_lux', 'goeun', 'ilwoo_space', 'koba', 'museum_hanmi', 'photo_sema', 'ryugaheon', 'sangsangmadang']
```

- [ ] **Step 3: Commit**

```bash
git add src/crawler/sources/__init__.py
git commit -m "feat(sources): register 7 new Korean gallery sources"
```

---

## Task 10: Pipeline integration smoke test

**Files:**
- Create: `tests/integration/test_pipeline_korea_galleries.py`

This test confirms that the new sources flow through normalize + resolver + a fake sink without raising, using each source's `list_page_1.html` fixture (or `list_all.html` for sangsangmadang, `list_current.html` for goeun). It does NOT assert specific row counts (those depend on the real-world fixture contents); it asserts no errors and at least one row per source.

- [ ] **Step 1: Write the test**

The authoritative reference is `tests/integration/test_pipeline_artmap.py`. The `run_source` signature is `run_source(extractor, repo, geocoder, today)`. Use the existing pytest fixtures `header_repo` (FakeHeaderRepo) and `null_geocoder` (NullGeocoder) from `tests/conftest.py`.

```python
"""Pipeline smoke for the 7 Korea-expansion sources.

For each new source, mock its list URL(s) with the captured fixture and
run the full pipeline (normalize + resolver + upsert into FakeHeaderRepo).
Assert: each source extracts ≥ 1 row, no failure, no errors.
"""

from __future__ import annotations

from datetime import date
from pathlib import Path

import httpx
import respx
from freezegun import freeze_time

from crawler.pipeline import run_source
from crawler.sinks.base import SheetName
from crawler.sources.canon_gallery import CanonGalleryExtractor
from crawler.sources.gallery_kong import GalleryKongExtractor
from crawler.sources.gallery_lux import GalleryLuxExtractor
from crawler.sources.goeun import GoeunExtractor
from crawler.sources.ilwoo_space import IlwooSpaceExtractor
from crawler.sources.ryugaheon import RyugaheonExtractor
from crawler.sources.sangsangmadang import SangsangmadangExtractor
from tests.conftest import FakeHeaderRepo, NullGeocoder

FIXTURE_ROOT = Path(__file__).parent.parent / "fixtures"


def _read(rel: str) -> str:
    return (FIXTURE_ROOT / rel).read_text(encoding="utf-8")


def _assert_clean(report) -> None:
    assert report.failure is None
    assert report.errors == 0
    assert report.extracted >= 1


@respx.mock
@freeze_time("2026-05-28")
def test_goeun_pipeline_smoke(header_repo: FakeHeaderRepo, null_geocoder: NullGeocoder):
    respx.get("https://www.goeunmuseum.org/exhibition/current").mock(
        return_value=httpx.Response(200, text=_read("goeun/list_current.html"))
    )
    respx.get("https://www.goeunmuseum.org/exhibition/upcoming").mock(
        return_value=httpx.Response(200, text=_read("goeun/list_upcoming.html"))
    )
    report = run_source(
        extractor=GoeunExtractor(delay_s=0.0),
        repo=header_repo,
        geocoder=null_geocoder,
        today=date(2026, 5, 28),
    )
    _assert_clean(report)
    assert len(header_repo.read_rows(SheetName.EXHIBITIONS)) == report.extracted


@respx.mock
@freeze_time("2026-05-28")
def test_gallery_lux_pipeline_smoke(header_repo: FakeHeaderRepo, null_geocoder: NullGeocoder):
    from crawler.sources.gallery_lux import _LIST_URL
    respx.get(_LIST_URL).mock(return_value=httpx.Response(200, text=_read("gallery_lux/list_page_1.html")))
    report = run_source(
        extractor=GalleryLuxExtractor(delay_s=0.0),
        repo=header_repo,
        geocoder=null_geocoder,
        today=date(2026, 5, 28),
    )
    _assert_clean(report)


@respx.mock
@freeze_time("2026-05-28")
def test_gallery_kong_pipeline_smoke(header_repo: FakeHeaderRepo, null_geocoder: NullGeocoder):
    from crawler.sources.gallery_kong import _LIST_URL
    respx.get(_LIST_URL).mock(return_value=httpx.Response(200, text=_read("gallery_kong/list_page_1.html")))
    report = run_source(
        extractor=GalleryKongExtractor(delay_s=0.0),
        repo=header_repo,
        geocoder=null_geocoder,
        today=date(2026, 5, 28),
    )
    _assert_clean(report)


@respx.mock
@freeze_time("2026-05-28")
def test_ryugaheon_pipeline_smoke(header_repo: FakeHeaderRepo, null_geocoder: NullGeocoder):
    from crawler.sources.ryugaheon import _LIST_URL
    respx.get(_LIST_URL).mock(return_value=httpx.Response(200, text=_read("ryugaheon/list_page_1.html")))
    report = run_source(
        extractor=RyugaheonExtractor(delay_s=0.0),
        repo=header_repo,
        geocoder=null_geocoder,
        today=date(2026, 5, 28),
    )
    _assert_clean(report)


@respx.mock
@freeze_time("2026-05-28")
def test_ilwoo_space_pipeline_smoke(header_repo: FakeHeaderRepo, null_geocoder: NullGeocoder):
    from crawler.sources.ilwoo_space import _LIST_URL
    respx.get(_LIST_URL).mock(return_value=httpx.Response(200, text=_read("ilwoo_space/list_page_1.html")))
    report = run_source(
        extractor=IlwooSpaceExtractor(delay_s=0.0),
        repo=header_repo,
        geocoder=null_geocoder,
        today=date(2026, 5, 28),
    )
    _assert_clean(report)


@respx.mock
@freeze_time("2026-05-28")
def test_sangsangmadang_pipeline_smoke(header_repo: FakeHeaderRepo, null_geocoder: NullGeocoder):
    from crawler.sources.sangsangmadang import _LIST_URL
    respx.get(_LIST_URL).mock(return_value=httpx.Response(200, text=_read("sangsangmadang/list_all.html")))
    report = run_source(
        extractor=SangsangmadangExtractor(delay_s=0.0),
        repo=header_repo,
        geocoder=null_geocoder,
        today=date(2026, 5, 28),
    )
    _assert_clean(report)


@respx.mock
@freeze_time("2026-05-28")
def test_canon_gallery_pipeline_smoke(header_repo: FakeHeaderRepo, null_geocoder: NullGeocoder):
    from crawler.sources.canon_gallery import _LIST_URL
    respx.get(_LIST_URL).mock(return_value=httpx.Response(200, text=_read("canon_gallery/list_page_1.html")))
    report = run_source(
        extractor=CanonGalleryExtractor(delay_s=0.0),
        repo=header_repo,
        geocoder=null_geocoder,
        today=date(2026, 5, 28),
    )
    _assert_clean(report)
```

If a per-source `_LIST_URL` is a tuple (e.g. goeun's `_LIST_URLS`), import the appropriate constant. If a source defines several list URLs, mock each one.

- [ ] **Step 2: Run integration test**

```bash
.venv/bin/pytest tests/integration/test_pipeline_korea_galleries.py -v
```

Expected: 7 passed.

- [ ] **Step 3: Commit**

```bash
git add tests/integration/test_pipeline_korea_galleries.py
git commit -m "test(integration): pipeline smoke for 7 Korea gallery sources"
```

---

## Task 11: Full verification

- [ ] **Step 1: Full pytest run**

```bash
.venv/bin/pytest -q
```

Expected: ~252 passed (217 baseline + ~35 new). No failures.

- [ ] **Step 2: ruff**

```bash
.venv/bin/ruff check src/ tests/
```

Expected: All checks passed!

- [ ] **Step 3: CLI smoke — list registered sources**

```bash
.venv/bin/crawler --help
```

Expected: help text mentions or supports the new source slugs. (`crawler run <slug>` and `crawler run-all` should work.)

- [ ] **Step 4: Dry-run each new source against fixtures (offline)**

The CLI `dry-run` command hits the live site. We don't run it here to avoid hammering production sites in dev. Real-site smoke happens in Task 12 after PR is open, on the user's manual trigger.

- [ ] **Step 5: Commit any final lint fixups (if any)**

If steps 1–2 surface drift, fix inline and commit:

```bash
git add -A
git commit -m "chore: lint/test cleanup for Korea gallery expansion"
```

---

## Task 12: Open PR

- [ ] **Step 1: Push branch**

```bash
git push -u origin feat/photo-sources-korea-expansion
```

- [ ] **Step 2: Open PR**

```bash
gh pr create --base main --title "feat: add 7 Korean photography gallery sources" --body "$(cat <<'EOF'
## Summary

- Adds 7 new source extractors for Korean photography galleries: 고은사진미술관, 갤러리 룩스, 공근혜갤러리, 류가헌, 일우스페이스, KT&G 상상마당, 캐논 갤러리.
- Sangsangmadang carries a source-level photo whitelist (mixed-media venue — only photo cards are emitted).
- `SourceName` enum extended; `run-all` auto-picks up the new sources via `__init__.py` import-time registration.
- No infra changes (no model schema beyond enum, no geocoder change, no workflow change).

Spec: `docs/superpowers/specs/2026-05-28-photo-sources-korea-expansion-design.md`
Plan: `docs/superpowers/plans/2026-05-28-photo-sources-korea-expansion.md`

## Test plan

- [ ] `pytest -q` — 252 pass, 0 fail
- [ ] `ruff check` — clean
- [ ] After merge: trigger crawl.yml workflow_dispatch and confirm 7 new sources appear in report.md with extracted ≥ 1 each
- [ ] After merge: `crawler backfill-geocodes` once to populate latitude/longitude for the 7 new venues

🤖 Generated with [Claude Code](https://claude.com/claude-code)
EOF
)"
```

Capture the PR URL from the output for the user.

---

## Self-review (run at end of writing this plan)

**Spec coverage:**
- §1 Scope (7 sites) → Tasks 2-8 ✓
- §3 source-level whitelist → Task 7 (sangsangmadang) ✓
- §4 module pattern → Conventions section + Task 2 ✓
- §5 testing (unit + integration + ~35 new) → Tasks 2-8 unit + Task 10 integration ✓
- §6.1 single PR → Task 12 ✓
- §6.3 backfill-geocodes note → Task 12 PR test plan ✓

**Placeholder scan:**
- `?ITEM_SELECTOR?` / `?TITLE_SELECTOR?` / `?DATE_SELECTOR?` in Task 2 step 7: intentional — selectors are discovered by inspecting real HTML in step 3. Same applies to `?CARD_SELECTOR?` / `?CATEGORY_SELECTOR?` in Task 7. These are the only fields the executor cannot pre-fill without seeing the page.
- `<URL FROM STEP 1>` in Tasks 3-8: same — URL verified at runtime against live site.
- Address fields (`_VENUE_ADDRESS`) are sometimes "verify from page footer" — same justification.
- No `TODO`, no "implement later", no "add appropriate error handling".

**Type consistency:**
- `RawExhibition` shape (source / source_url / raw) used identically in every site task ✓
- `SourceName.X` value matches enum entry in Task 1 ✓
- Class name pattern `<SiteName>Extractor` consistent ✓

**Site URL escalation path:** Every Task step 1 instructs to STOP and escalate if the candidate URLs fail or the site is JS-only — this prevents wasted effort on broken sites.
