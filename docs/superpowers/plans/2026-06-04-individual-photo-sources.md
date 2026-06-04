# Individual-Photographer Photo-Gallery Sources Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add 4 plain-HTTP-SSR photo-only gallery sources (Place M, Totem Pole, Gallery Tosei, Art Space J) that host solo shows by individual photographers, so the crawler captures independent-artist exhibitions.

**Architecture:** Each source is one self-contained module in `src/crawler/sources/` following the existing extractor pattern (httpx client + tenacity retry, pure `_parse_list`/`_parse_detail` functions, `crawl()` yielding `RawExhibition`, `register_source(...)` at the bottom). No new normalization code — all 4 are 100% photography, so we seed `raw["category"]` with a photo keyword and let the existing `map_medium` classify. Dotted/`~` dates use the shared `extract_date_range`; JP `年月日` dates use a source-local parser copied from `zen_foto`.

**Tech Stack:** Python 3.12, httpx, selectolax, tenacity, respx (tests), pytest, ruff.

---

## Conventions every task follows

- **Capture the fixture from the live site first** (each task's Step 1). The parser code below is written against the date/title formats observed in recon (2026-06-04), using robust anchor-iteration + regex (no fragile CSS class names). After capturing the fixture, run the unit test; if a real-page detail differs (e.g. the poster `<img>` isn't the first one, or the date sits in a sibling node), adjust the one flagged spot and update the expected values in the test to match the captured fixture. The test values below come from recon samples — **treat them as the starting expectation and reconcile with the actual fixture.**
- Fixtures live in `tests/fixtures/<source>/`. Tests live in `tests/sources/test_<source>.py`.
- The shared `_USER_AGENT` (desktop Chrome string) is copied per module exactly as in `pgi.py`.
- CI gate is `ruff check src/ tests/` + `pytest -q`. mypy is **not** in CI — the `register_source` Protocol arg-type and pydantic `source_url=str` patterns are accepted; don't chase mypy.
- After each task: `ruff check src/ tests/` and `pytest -q` must pass before committing.

---

## Task 1: `place_m` — Place M / プレイスM (JP, artist-run, 100% photo)

**Files:**
- Create: `src/crawler/sources/place_m.py`
- Modify: `src/crawler/models.py` (add `PLACE_M = "place_m"` to `SourceName`)
- Modify: `src/crawler/sources/__init__.py` (add `place_m,  # noqa: F401`)
- Create: `tests/fixtures/place_m/list.html`, `tests/fixtures/place_m/detail.html`
- Test: `tests/sources/test_place_m.py`

- [ ] **Step 1: Capture live fixtures**

```bash
UA='Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Safari/537.36'
mkdir -p tests/fixtures/place_m
curl -sL -A "$UA" 'https://www.placem.com/schedule/schedule.php' -o tests/fixtures/place_m/list.html
# Pick one current exhibition detail href from the list and save it (replace the path):
curl -sL -A "$UA" 'https://www.placem.com/schedule/2026/main/20260601/exhibition.php' -o tests/fixtures/place_m/detail.html
```
Open `list.html`, confirm it contains anchors like `../schedule/2026/main/20260601/exhibition.php` and text `星玄人「西成」` + date `2026.06.01 - 2026.06.07`. Note the actual detail URL you saved for the test.

- [ ] **Step 2: Add the `SourceName` member**

In `src/crawler/models.py`, inside `class SourceName(StrEnum)`, add after the existing members:

```python
    PLACE_M = "place_m"
```

- [ ] **Step 3: Write the failing test**

Create `tests/sources/test_place_m.py`:

```python
from pathlib import Path

import httpx
import respx

from crawler.models import SourceName
from crawler.sources.place_m import PlaceMExtractor, _parse_detail, _parse_list

FIXTURE_DIR = Path(__file__).parent.parent / "fixtures" / "place_m"


def _list_html() -> str:
    return (FIXTURE_DIR / "list.html").read_text(encoding="utf-8")


def _detail_html() -> str:
    return (FIXTURE_DIR / "detail.html").read_text(encoding="utf-8")


def test_parse_list_extracts_title_artist_date_url():
    items = _parse_list(_list_html())
    assert items, "expected at least one exhibition"
    first = items[0]
    assert first["source_url"].startswith("https://www.placem.com/schedule/")
    assert first["source_url"].endswith("/exhibition.php")
    # Title comes from inside 「」; artist from before it.
    assert first["title"]
    assert "「" not in first["title"] and "」" not in first["title"]
    # Date canonicalized to YYYY.MM.DD~YYYY.MM.DD (reconcile with fixture).
    assert first["date_range"] is None or "~" in first["date_range"]


def test_parse_list_dedupes_urls():
    items = _parse_list(_list_html())
    urls = [it["source_url"] for it in items]
    assert len(urls) == len(set(urls))


def test_parse_detail_returns_poster_and_description():
    d = _parse_detail(_detail_html())
    assert "poster_image_url" in d and "description" in d


@respx.mock
def test_crawl_yields_normalized_raws():
    respx.get("https://www.placem.com/schedule/schedule.php").mock(
        return_value=httpx.Response(200, text=_list_html())
    )
    respx.route(method="GET", url__regex=r"placem\.com/schedule/\d{4}/.+").mock(
        return_value=httpx.Response(200, text=_detail_html())
    )
    raws = list(PlaceMExtractor(delay_s=0.0).crawl())
    assert raws
    assert all(r.source is SourceName.PLACE_M for r in raws)
    assert all(r.raw["category"] == "写真" for r in raws)
    assert all(r.raw["venue_region"] == "東京" for r in raws)
```

- [ ] **Step 4: Run the test to verify it fails**

Run: `pytest tests/sources/test_place_m.py -q`
Expected: FAIL with `ModuleNotFoundError: No module named 'crawler.sources.place_m'`.

- [ ] **Step 5: Write the module**

Create `src/crawler/sources/place_m.py`:

```python
"""Place M / プレイスM (placem.com) — HTML extractor.

Strategy (recon 2026-06-04):
An artist-run photography gallery + darkroom in Shinjuku, Tokyo — every show is
photography, so we seed the medium text and skip genre filtering. The static
``/schedule/schedule.php`` page lists each show as an anchor to
``../schedule/<YYYY>/main/<YYYYMMDD>/exhibition.php`` with text
``作家「タイトル」`` followed by a dotted date span ``2026.06.01 - 2026.06.07``.
Detail pages expose no og:image, so the poster comes from the first content
``<img>``.
"""

from __future__ import annotations

import re
import time
import urllib.parse
from collections.abc import Iterable

import httpx
from selectolax.parser import HTMLParser
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

from crawler.models import RawExhibition, SourceName
from crawler.normalize.text import clean_whitespace
from crawler.sources._detail import extract_date_range, meta_description, paragraphs_text
from crawler.sources.base import register_source

_BASE_URL = "https://www.placem.com"
_LIST_URL = f"{_BASE_URL}/schedule/schedule.php"
_USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Safari/537.36"
)

_VENUE_NAME = "Place M"
_VENUE_REGION = "東京"
_VENUE_ADDRESS = "東京都新宿区新宿1-2-11 第二都ビル3F"

_HREF_RE = re.compile(r"schedule/\d{4}/main/\d{8}/exhibition\.php")
_TITLE_RE = re.compile(r"「(.+?)」")


def _absolute(href: str) -> str:
    return urllib.parse.urljoin(_LIST_URL, href)


def _split_artist_title(text: str) -> tuple[list[str], str]:
    """``作家「タイトル」`` -> (["作家"], "タイトル"). Falls back to whole text."""
    tm = _TITLE_RE.search(text)
    if not tm:
        return [], clean_whitespace(text)
    title = clean_whitespace(tm.group(1))
    artist = clean_whitespace(text[: tm.start()])
    return ([artist] if artist else []), (title or clean_whitespace(text))


def _parse_list(html: str) -> list[dict]:
    """Return one ``{source_url, title, artists, date_range}`` per exhibition."""
    doc = HTMLParser(html)
    items: list[dict] = []
    seen: set[str] = set()
    for a in doc.css("a"):
        href = a.attributes.get("href") or ""
        if not _HREF_RE.search(href):
            continue
        url = _absolute(href)
        if url in seen:
            continue
        seen.add(url)
        text = clean_whitespace(a.text())
        # The date may sit in the anchor text or in the surrounding row.
        row = a.parent
        row_text = clean_whitespace(row.text()) if row is not None else text
        source = text if "「" in text else row_text
        artists, title = _split_artist_title(source)
        if not title:
            continue
        date_range = extract_date_range(text) or extract_date_range(row_text)
        items.append(
            {
                "source_url": url,
                "title": title,
                "artists": artists,
                "date_range": date_range,
            }
        )
    return items


def _parse_detail(html: str) -> dict:
    """Poster from the first content ``<img>`` (no og:image); body prose."""
    doc = HTMLParser(html)
    poster = None
    og = doc.css_first('meta[property="og:image"]')
    if og is not None:
        poster = clean_whitespace(og.attributes.get("content") or "") or None
    if poster is None:
        for img in doc.css("img"):
            src = img.attributes.get("src") or ""
            if not src or src.endswith(".gif"):  # skip spacers/logos
                continue
            poster = urllib.parse.urljoin(_BASE_URL, src)
            break
    body = doc.css_first("body")
    description = None
    if body is not None:
        text = paragraphs_text(body)
        description = text or meta_description(doc)
    return {"poster_image_url": poster, "description": description}


class PlaceMExtractor:
    name = SourceName.PLACE_M
    country = "JP"

    def __init__(self, delay_s: float = 1.0, timeout_s: float = 30.0) -> None:
        self.delay_s = delay_s
        self._client = httpx.Client(
            timeout=timeout_s,
            headers={
                "User-Agent": _USER_AGENT,
                "Accept-Language": "ja,en-US;q=0.8,en;q=0.7",
            },
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
        for item in _parse_list(self._get(_LIST_URL)):
            try:
                detail = _parse_detail(self._get(item["source_url"]))
            except Exception:  # noqa: BLE001 — one bad detail must not abort the run
                detail = {"poster_image_url": None, "description": None}
            raw = {
                "title": item["title"],
                "category": "写真",
                "date_range": item["date_range"],
                "venue_name": _VENUE_NAME,
                "venue_region": _VENUE_REGION,
                "venue_address": _VENUE_ADDRESS,
                "poster_image_url": detail["poster_image_url"],
                "description": detail["description"],
                "artists": item["artists"],
            }
            yield RawExhibition(
                source=SourceName.PLACE_M,
                source_url=item["source_url"],
                raw=raw,
            )
            if self.delay_s > 0:
                time.sleep(self.delay_s)


register_source(SourceName.PLACE_M, PlaceMExtractor)
```

- [ ] **Step 6: Register the module**

In `src/crawler/sources/__init__.py`, add `place_m,  # noqa: F401` to the import tuple (alphabetical: after `pgi,`).

- [ ] **Step 7: Run the test to verify it passes**

Run: `pytest tests/sources/test_place_m.py -q`
Expected: PASS. If `test_parse_detail` shows the poster picked a logo, narrow the `<img>` selector to the main content container you see in `detail.html` and re-run.

- [ ] **Step 8: Lint + full suite**

Run: `ruff check src/ tests/ && pytest -q`
Expected: PASS (no new failures).

- [ ] **Step 9: Commit**

```bash
git add src/crawler/sources/place_m.py src/crawler/models.py src/crawler/sources/__init__.py tests/sources/test_place_m.py tests/fixtures/place_m/
git commit -m "feat(sources): add Place M (placem.com) photo-gallery source"
```

---

## Task 2: `totem_pole` — Totem Pole Photo Gallery / TPPG (JP, artist-run, 100% photo)

**Files:**
- Create: `src/crawler/sources/totem_pole.py`
- Modify: `src/crawler/models.py` (add `TOTEM_POLE = "totem_pole"`)
- Modify: `src/crawler/sources/__init__.py` (add `totem_pole,  # noqa: F401`)
- Create: `tests/fixtures/totem_pole/list.html`, `tests/fixtures/totem_pole/detail.html`
- Test: `tests/sources/test_totem_pole.py`

- [ ] **Step 1: Capture live fixtures**

```bash
UA='Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Safari/537.36'
mkdir -p tests/fixtures/totem_pole
curl -sL -A "$UA" 'https://tppg.jp/' -o tests/fixtures/totem_pole/list.html
# Pick one current exhibition slug visible on the homepage and save it:
curl -sL -A "$UA" 'https://tppg.jp/choosing-facts-2024/' -o tests/fixtures/totem_pole/detail.html
```
Confirm `list.html` contains current/upcoming entries like `蔡嘉辰 / Jiachen Cai "Sunburn"` with `2026.5.26 (tue) – 6.7 (sun)` and flat-slug links `/<slug>/`. Note one real slug for the test.

- [ ] **Step 2: Add the `SourceName` member**

In `src/crawler/models.py`, add to `SourceName`:

```python
    TOTEM_POLE = "totem_pole"
```

- [ ] **Step 3: Write the failing test**

Create `tests/sources/test_totem_pole.py`:

```python
from pathlib import Path

import httpx
import respx

from crawler.models import SourceName
from crawler.sources.totem_pole import (
    TotemPoleExtractor,
    _parse_detail,
    _parse_list,
)

FIXTURE_DIR = Path(__file__).parent.parent / "fixtures" / "totem_pole"


def _list_html() -> str:
    return (FIXTURE_DIR / "list.html").read_text(encoding="utf-8")


def _detail_html() -> str:
    return (FIXTURE_DIR / "detail.html").read_text(encoding="utf-8")


def test_parse_list_finds_dated_exhibitions():
    items = _parse_list(_list_html())
    assert items, "expected at least one current/upcoming exhibition"
    for it in items:
        assert it["source_url"].startswith("https://tppg.jp/")
        assert it["title"]
    # At least one item carries a canonical date span.
    assert any(it["date_range"] and "~" in it["date_range"] for it in items)


def test_parse_list_dedupes_and_excludes_nav():
    items = _parse_list(_list_html())
    urls = [it["source_url"] for it in items]
    assert len(urls) == len(set(urls))
    # Nav/utility pages must not be treated as exhibitions.
    for bad in ("/about/", "/access/", "/contact/", "/exhibitions/"):
        assert all(not u.endswith(bad) for u in urls)


def test_parse_detail_returns_poster_and_description():
    d = _parse_detail(_detail_html())
    assert "poster_image_url" in d and "description" in d


@respx.mock
def test_crawl_yields_normalized_raws():
    respx.get("https://tppg.jp/").mock(
        return_value=httpx.Response(200, text=_list_html())
    )
    respx.route(method="GET", url__regex=r"tppg\.jp/[^/]+/$").mock(
        return_value=httpx.Response(200, text=_detail_html())
    )
    raws = list(TotemPoleExtractor(delay_s=0.0).crawl())
    assert raws
    assert all(r.source is SourceName.TOTEM_POLE for r in raws)
    assert all(r.raw["category"] == "写真" for r in raws)
```

- [ ] **Step 4: Run the test to verify it fails**

Run: `pytest tests/sources/test_totem_pole.py -q`
Expected: FAIL with `ModuleNotFoundError: No module named 'crawler.sources.totem_pole'`.

- [ ] **Step 5: Write the module**

Create `src/crawler/sources/totem_pole.py`:

```python
"""Totem Pole Photo Gallery / TPPG (tppg.jp) — HTML extractor.

Strategy (recon 2026-06-04):
An artist-run photography gallery in Shinjuku, Tokyo (100% photo). The
WordPress homepage server-renders the current + upcoming shows inline: each is
an anchor to a flat slug page ``https://tppg.jp/<slug>/`` whose surrounding text
carries ``作家 / Artist "Title" 2026.5.26 (tue) – 6.7 (sun)``. We keep only
anchors whose nearby text contains a dotted date span, which naturally excludes
nav/utility links. Detail pages are WordPress so og:image is usually present.
"""

from __future__ import annotations

import re
import time
import urllib.parse
from collections.abc import Iterable

import httpx
from selectolax.parser import HTMLParser
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

from crawler.models import RawExhibition, SourceName
from crawler.normalize.text import clean_whitespace
from crawler.sources._detail import extract_date_range, meta_description, paragraphs_text
from crawler.sources.base import register_source

_BASE_URL = "https://tppg.jp"
_LIST_URL = f"{_BASE_URL}/"
_USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Safari/537.36"
)

_VENUE_NAME = "Totem Pole Photo Gallery"
_VENUE_REGION = "東京"
_VENUE_ADDRESS = "東京都新宿区新宿2-12-14 1F"

# Flat single-segment slug pages, e.g. https://tppg.jp/choosing-facts-2024/
_SLUG_RE = re.compile(r"^https?://tppg\.jp/([^/]+)/$")
# Slugs that are site chrome, not exhibitions.
_STOP_SLUGS = {
    "about", "access", "contact", "exhibitions", "upcoming", "past",
    "archive", "news", "shop", "category", "tag", "wp", "en", "privacy",
}
# Title appears inside straight or Japanese quotes.
_TITLE_RE = re.compile(r"[\"“”「『](.+?)[\"“”」』]")
# A dotted date span signals this anchor is an exhibition row.
_HAS_DATE_RE = re.compile(r"\d{4}\s*\.\s*\d{1,2}\s*\.\s*\d{1,2}")


def _split_artist_title(text: str) -> tuple[list[str], str]:
    tm = _TITLE_RE.search(text)
    if tm:
        title = clean_whitespace(tm.group(1))
        artist = clean_whitespace(text[: tm.start()])
        return ([artist] if artist else []), (title or clean_whitespace(text))
    # No quotes: strip the trailing date token off the whole string.
    dm = _HAS_DATE_RE.search(text)
    title = clean_whitespace(text[: dm.start()]) if dm else clean_whitespace(text)
    return [], (title or clean_whitespace(text))


def _parse_list(html: str) -> list[dict]:
    doc = HTMLParser(html)
    items: list[dict] = []
    seen: set[str] = set()
    for a in doc.css("a"):
        href = a.attributes.get("href") or ""
        url = urllib.parse.urljoin(_BASE_URL + "/", href)
        m = _SLUG_RE.match(url)
        if not m or m.group(1).lower() in _STOP_SLUGS:
            continue
        if url in seen:
            continue
        # Require a date in the anchor or its container -> it's an exhibition.
        text = clean_whitespace(a.text())
        row = a.parent
        row_text = clean_whitespace(row.text()) if row is not None else text
        source = text if _HAS_DATE_RE.search(text) else row_text
        if not _HAS_DATE_RE.search(source):
            continue
        seen.add(url)
        artists, title = _split_artist_title(source)
        if not title:
            continue
        items.append(
            {
                "source_url": url,
                "title": title,
                "artists": artists,
                "date_range": extract_date_range(source),
            }
        )
    return items


def _parse_detail(html: str) -> dict:
    doc = HTMLParser(html)
    poster = None
    og = doc.css_first('meta[property="og:image"]')
    if og is not None:
        poster = clean_whitespace(og.attributes.get("content") or "") or None
    if poster is None:
        for img in doc.css("img"):
            src = img.attributes.get("src") or ""
            if src and not src.endswith(".gif"):
                poster = urllib.parse.urljoin(_BASE_URL, src)
                break
    body = doc.css_first("body")
    description = (paragraphs_text(body) if body is not None else None) or meta_description(doc)
    return {"poster_image_url": poster, "description": description}


class TotemPoleExtractor:
    name = SourceName.TOTEM_POLE
    country = "JP"

    def __init__(self, delay_s: float = 1.0, timeout_s: float = 30.0) -> None:
        self.delay_s = delay_s
        self._client = httpx.Client(
            timeout=timeout_s,
            headers={
                "User-Agent": _USER_AGENT,
                "Accept-Language": "ja,en-US;q=0.8,en;q=0.7",
            },
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
        for item in _parse_list(self._get(_LIST_URL)):
            try:
                detail = _parse_detail(self._get(item["source_url"]))
            except Exception:  # noqa: BLE001
                detail = {"poster_image_url": None, "description": None}
            raw = {
                "title": item["title"],
                "category": "写真",
                "date_range": item["date_range"],
                "venue_name": _VENUE_NAME,
                "venue_region": _VENUE_REGION,
                "venue_address": _VENUE_ADDRESS,
                "poster_image_url": detail["poster_image_url"],
                "description": detail["description"],
                "artists": item["artists"],
            }
            yield RawExhibition(
                source=SourceName.TOTEM_POLE,
                source_url=item["source_url"],
                raw=raw,
            )
            if self.delay_s > 0:
                time.sleep(self.delay_s)


register_source(SourceName.TOTEM_POLE, TotemPoleExtractor)
```

- [ ] **Step 6: Register the module**

In `src/crawler/sources/__init__.py`, add `totem_pole,  # noqa: F401` (alphabetical: after `tokyo_photographic_art_museum,`).

- [ ] **Step 7: Run the test to verify it passes**

Run: `pytest tests/sources/test_totem_pole.py -q`
Expected: PASS. If `_parse_list` returns nav links or misses real shows, tighten `_STOP_SLUGS` / confirm the date lives in the anchor's parent vs. a higher ancestor (walk to `a.parent.parent` if needed) against `list.html`.

- [ ] **Step 8: Lint + full suite**

Run: `ruff check src/ tests/ && pytest -q`
Expected: PASS.

- [ ] **Step 9: Commit**

```bash
git add src/crawler/sources/totem_pole.py src/crawler/models.py src/crawler/sources/__init__.py tests/sources/test_totem_pole.py tests/fixtures/totem_pole/
git commit -m "feat(sources): add Totem Pole Photo Gallery (tppg.jp) source"
```

---

## Task 3: `gallery_tosei` — Gallery Tosei / ギャラリー冬青 (JP, 100% photo, Shift_JIS)

**Files:**
- Create: `src/crawler/sources/gallery_tosei.py`
- Modify: `src/crawler/models.py` (add `GALLERY_TOSEI = "gallery_tosei"`)
- Modify: `src/crawler/sources/__init__.py` (add `gallery_tosei,  # noqa: F401`)
- Create: `tests/fixtures/gallery_tosei/list.html`
- Test: `tests/sources/test_gallery_tosei.py`

> **Encoding note:** this site is **http-only and Shift_JIS**. The fixture must be saved as UTF-8 so the repo/tests stay UTF-8, and `_get` must decode the live bytes from Shift_JIS. The parser receives a decoded `str` either way, so `_parse_list` is encoding-agnostic.

- [ ] **Step 1: Capture live fixture (decode Shift_JIS → save UTF-8)**

```bash
UA='Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Safari/537.36'
mkdir -p tests/fixtures/gallery_tosei
curl -sL -A "$UA" 'http://www.tosei-sha.jp/TOSEI-NEW-HP/html/EXHIBITIONS/j_exhibitions.html' \
  | iconv -f SHIFT_JIS -t UTF-8 > tests/fixtures/gallery_tosei/list.html
```
Confirm `list.html` shows e.g. `黒岩玲人写真展「眠りといっしょに」`, `2026年6月28日(日) - 7月12日(日)`, an `<img src="../../jpg/EXHIBITIONS/...jpg">`, and a detail href `../../html/EXHIBITIONS/j_<Name>.html`.

- [ ] **Step 2: Add the `SourceName` member**

In `src/crawler/models.py`, add to `SourceName`:

```python
    GALLERY_TOSEI = "gallery_tosei"
```

- [ ] **Step 3: Write the failing test**

Create `tests/sources/test_gallery_tosei.py`:

```python
from pathlib import Path

import httpx
import respx

from crawler.models import SourceName
from crawler.sources.gallery_tosei import (
    GalleryToseiExtractor,
    _extract_jp_date_range,
    _parse_list,
)

FIXTURE_DIR = Path(__file__).parent.parent / "fixtures" / "gallery_tosei"
_LIST_URL = (
    "http://www.tosei-sha.jp/TOSEI-NEW-HP/html/EXHIBITIONS/j_exhibitions.html"
)


def _list_html() -> str:
    return (FIXTURE_DIR / "list.html").read_text(encoding="utf-8")


def test_extract_jp_date_range_full():
    assert _extract_jp_date_range("2026年6月28日(日) - 7月12日(日)") == "2026.06.28~2026.07.12"


def test_extract_jp_date_range_yearless_end_backfilled():
    assert _extract_jp_date_range("2026年7月14日(日) - 8月1日(土)") == "2026.07.14~2026.08.01"


def test_extract_jp_date_range_none_when_absent():
    assert _extract_jp_date_range("作家略歴のみ") is None


def test_parse_list_extracts_title_date_poster_url():
    items = _parse_list(_list_html())
    assert items, "expected current + next show"
    first = items[0]
    assert first["title"]
    assert first["source_url"].startswith("http://www.tosei-sha.jp/")
    assert first["date_range"] is None or "~" in first["date_range"]
    # Poster resolved to an absolute http URL when present.
    assert first["poster_image_url"] is None or first["poster_image_url"].startswith("http")


@respx.mock
def test_crawl_yields_normalized_raws():
    respx.get(_LIST_URL).mock(return_value=httpx.Response(200, text=_list_html()))
    # Detail pages may 404 for freshly-announced shows; listing is enough.
    respx.route(method="GET", url__regex=r"tosei-sha\.jp/.+/j_.+\.html").mock(
        return_value=httpx.Response(404)
    )
    raws = list(GalleryToseiExtractor(delay_s=0.0).crawl())
    assert raws
    assert all(r.source is SourceName.GALLERY_TOSEI for r in raws)
    assert all(r.raw["category"] == "写真" for r in raws)
    assert all(r.raw["venue_region"] == "東京" for r in raws)
```

- [ ] **Step 4: Run the test to verify it fails**

Run: `pytest tests/sources/test_gallery_tosei.py -q`
Expected: FAIL with `ModuleNotFoundError`.

- [ ] **Step 5: Write the module**

Create `src/crawler/sources/gallery_tosei.py`:

```python
"""Gallery Tosei / ギャラリー冬青 (tosei-sha.jp) — HTML extractor.

Strategy (recon 2026-06-04):
A photography-only gallery run by the publisher 冬青社 in Tokyo. The site is a
hand-maintained static site that is **http-only and Shift_JIS-encoded**, so we
decode the bytes from Shift_JIS in ``_get``. The current + next show live on
``.../EXHIBITIONS/j_exhibitions.html`` as ``作家写真展「タイトル」`` with a
``YYYY年M月D日(曜) - M月D日(曜)`` span, a poster ``<img>`` (relative ``../../jpg``)
and a detail href ``../../html/EXHIBITIONS/j_<Name>.html`` (which may 404 for a
freshly-announced show, so the listing alone carries title/date/image).

Dates use the JP ``年月日`` form, so we keep a source-local parser (copied from
``zen_foto``); running the dotted ``extract_date_range`` on this body would
misread artist birth-years.
"""

from __future__ import annotations

import re
import time
import urllib.parse
from collections.abc import Iterable
from datetime import date

import httpx
from selectolax.parser import HTMLParser
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

from crawler.models import RawExhibition, SourceName
from crawler.normalize.text import clean_whitespace
from crawler.sources._detail import paragraphs_text
from crawler.sources.base import register_source

_BASE_URL = "http://www.tosei-sha.jp"
_LIST_URL = f"{_BASE_URL}/TOSEI-NEW-HP/html/EXHIBITIONS/j_exhibitions.html"
_USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Safari/537.36"
)

_VENUE_NAME = "Gallery Tosei"
_VENUE_REGION = "東京"
_VENUE_ADDRESS = "東京都中野区中央5-18-20"

_DETAIL_HREF_RE = re.compile(r"EXHIBITIONS/j_[^/\"']+\.html$")
_TITLE_RE = re.compile(r"[「『](.+?)[」』]")
_JP_RANGE_RE = re.compile(
    r"(\d{4})\s*年\s*(\d{1,2})\s*月\s*(\d{1,2})\s*日"
    r"[^0-9年]*?"
    r"(?:(\d{4})\s*年\s*)?"
    r"(?:(\d{1,2})\s*月\s*)?"
    r"(\d{1,2})\s*日"
)


def _extract_jp_date_range(text: str) -> str | None:
    m = _JP_RANGE_RE.search(text)
    if not m:
        return None
    sy, sm, sd = int(m.group(1)), int(m.group(2)), int(m.group(3))
    ey = int(m.group(4)) if m.group(4) else sy
    em = int(m.group(5)) if m.group(5) else sm
    ed = int(m.group(6))
    try:
        date(sy, sm, sd)
        date(ey, em, ed)
    except ValueError:
        return None
    return f"{sy:04d}.{sm:02d}.{sd:02d}~{ey:04d}.{em:02d}.{ed:02d}"


def _parse_list(html: str) -> list[dict]:
    """Return one ``{source_url, title, date_range, poster_image_url}`` per show.

    Each show is a block holding a detail anchor; we read title/date from the
    block text and the poster from the nearest ``<img>``.
    """
    doc = HTMLParser(html)
    items: list[dict] = []
    seen: set[str] = set()
    for a in doc.css("a"):
        href = a.attributes.get("href") or ""
        if not _DETAIL_HREF_RE.search(href):
            continue
        url = urllib.parse.urljoin(_LIST_URL, href)
        if url in seen:
            continue
        # Climb to the enclosing block (table cell / div) for title+date+img.
        block = a.parent
        for _ in range(3):
            if block is None or block.parent is None:
                break
            if _JP_RANGE_RE.search(clean_whitespace(block.text())):
                break
            block = block.parent
        block = block if block is not None else a
        block_text = clean_whitespace(block.text())
        date_range = _extract_jp_date_range(block_text)
        tm = _TITLE_RE.search(block_text)
        title = clean_whitespace(tm.group(1)) if tm else clean_whitespace(a.text())
        if not title:
            continue
        seen.add(url)
        poster = None
        img = block.css_first("img") if hasattr(block, "css_first") else None
        if img is not None:
            src = img.attributes.get("src") or ""
            if src:
                poster = urllib.parse.urljoin(_LIST_URL, src)
        items.append(
            {
                "source_url": url,
                "title": title,
                "date_range": date_range,
                "poster_image_url": poster,
            }
        )
    return items


def _parse_detail(html: str) -> dict:
    doc = HTMLParser(html)
    body = doc.css_first("body")
    description = paragraphs_text(body) if body is not None else None
    return {"description": description or None}


class GalleryToseiExtractor:
    name = SourceName.GALLERY_TOSEI
    country = "JP"

    def __init__(self, delay_s: float = 1.0, timeout_s: float = 30.0) -> None:
        self.delay_s = delay_s
        self._client = httpx.Client(
            timeout=timeout_s,
            headers={
                "User-Agent": _USER_AGENT,
                "Accept-Language": "ja,en-US;q=0.8,en;q=0.7",
            },
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
        # Site is Shift_JIS; decode explicitly (httpx may mis-detect).
        return r.content.decode("shift_jis", errors="replace")

    def crawl(self) -> Iterable[RawExhibition]:
        for item in _parse_list(self._get(_LIST_URL)):
            description = None
            try:
                description = _parse_detail(self._get(item["source_url"]))["description"]
            except Exception:  # noqa: BLE001 — detail may 404 for new shows
                description = None
            raw = {
                "title": item["title"],
                "category": "写真",
                "date_range": item["date_range"],
                "venue_name": _VENUE_NAME,
                "venue_region": _VENUE_REGION,
                "venue_address": _VENUE_ADDRESS,
                "poster_image_url": item["poster_image_url"],
                "description": description,
                "artists": [],
            }
            yield RawExhibition(
                source=SourceName.GALLERY_TOSEI,
                source_url=item["source_url"],
                raw=raw,
            )
            if self.delay_s > 0:
                time.sleep(self.delay_s)


register_source(SourceName.GALLERY_TOSEI, GalleryToseiExtractor)
```

- [ ] **Step 6: Register the module**

In `src/crawler/sources/__init__.py`, add `gallery_tosei,  # noqa: F401` (alphabetical: after `gallery_lux,`).

- [ ] **Step 7: Run the test to verify it passes**

Run: `pytest tests/sources/test_gallery_tosei.py -q`
Expected: PASS. If `_parse_list` returns 0 items, the detail anchors may not match `_DETAIL_HREF_RE` — inspect the real href in `list.html` and widen the regex. If title/date come from the wrong block, adjust the climb depth (the `range(3)` loop).

- [ ] **Step 8: Lint + full suite**

Run: `ruff check src/ tests/ && pytest -q`
Expected: PASS.

- [ ] **Step 9: Commit**

```bash
git add src/crawler/sources/gallery_tosei.py src/crawler/models.py src/crawler/sources/__init__.py tests/sources/test_gallery_tosei.py tests/fixtures/gallery_tosei/
git commit -m "feat(sources): add Gallery Tosei (tosei-sha.jp) photo source"
```

---

## Task 4: `art_space_j` — Art Space J / 아트스페이스 J (KR, 100% photo)

**Files:**
- Create: `src/crawler/sources/art_space_j.py`
- Modify: `src/crawler/models.py` (add `ART_SPACE_J = "art_space_j"`)
- Modify: `src/crawler/sources/__init__.py` (add `art_space_j,  # noqa: F401`)
- Create: `tests/fixtures/art_space_j/list_current.html`, `tests/fixtures/art_space_j/detail.html`
- Test: `tests/sources/test_art_space_j.py`

> **Transport note:** HTTPS uses a self-signed cert and the HTTPS root WAF-returns 406; use the **http** `/sub/*.php` paths with a browser UA. We crawl current (`sub03_01.php`) + upcoming (`sub03_03.php`); past is out of scope for this round.

- [ ] **Step 1: Capture live fixtures**

```bash
UA='Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Safari/537.36'
mkdir -p tests/fixtures/art_space_j
curl -sL -A "$UA" 'http://www.artspacej.com/sub/sub03_01.php?boardid=exhib' -o tests/fixtures/art_space_j/list_current.html
# Pick one detail idx visible in the list and save it (replace idx):
curl -sL -A "$UA" 'http://www.artspacej.com/sub/sub03_01.php?boardid=exhib&mode=view&idx=238' -o tests/fixtures/art_space_j/detail.html
```
Confirm `list_current.html` shows entries like `[CUBE1]김영진 개인전_당신의 마음에도 꽃이 피기를` with `2026.03.06 ~ 2026.04.30` and a `mode=view&idx=<n>` href.

- [ ] **Step 2: Add the `SourceName` member**

In `src/crawler/models.py`, add to `SourceName`:

```python
    ART_SPACE_J = "art_space_j"
```

- [ ] **Step 3: Write the failing test**

Create `tests/sources/test_art_space_j.py`:

```python
from pathlib import Path

import httpx
import respx

from crawler.models import SourceName
from crawler.sources.art_space_j import (
    ArtSpaceJExtractor,
    _clean_title,
    _parse_detail,
    _parse_list,
)

FIXTURE_DIR = Path(__file__).parent.parent / "fixtures" / "art_space_j"


def _list_html() -> str:
    return (FIXTURE_DIR / "list_current.html").read_text(encoding="utf-8")


def _detail_html() -> str:
    return (FIXTURE_DIR / "detail.html").read_text(encoding="utf-8")


def test_clean_title_strips_room_tag_and_trailing_date():
    raw = "[CUBE1]김영진 개인전_당신의 마음에도 꽃이 피기를_2026.03.06-04.30"
    assert _clean_title(raw) == "김영진 개인전_당신의 마음에도 꽃이 피기를"


def test_parse_list_extracts_title_date_url():
    items = _parse_list(_list_html())
    assert items
    first = items[0]
    assert "[CUBE" not in first["title"]
    assert first["source_url"].startswith("http://www.artspacej.com/")
    assert "mode=view" in first["source_url"]
    assert first["date_range"] is None or "~" in first["date_range"]


def test_parse_list_dedupes():
    items = _parse_list(_list_html())
    urls = [it["source_url"] for it in items]
    assert len(urls) == len(set(urls))


def test_parse_detail_returns_poster_and_description():
    d = _parse_detail(_detail_html())
    assert "poster_image_url" in d and "description" in d


@respx.mock
def test_crawl_yields_normalized_raws():
    respx.route(method="GET", url__regex=r"artspacej\.com/sub/sub03_0[13]\.php\?boardid=exhib$").mock(
        return_value=httpx.Response(200, text=_list_html())
    )
    respx.route(method="GET", url__regex=r"artspacej\.com/sub/.+mode=view.+").mock(
        return_value=httpx.Response(200, text=_detail_html())
    )
    raws = list(ArtSpaceJExtractor(delay_s=0.0).crawl())
    assert raws
    assert all(r.source is SourceName.ART_SPACE_J for r in raws)
    assert all(r.raw["category"] == "사진" for r in raws)
    assert all(r.raw["venue_region"] == "성남" for r in raws)
```

- [ ] **Step 4: Run the test to verify it fails**

Run: `pytest tests/sources/test_art_space_j.py -q`
Expected: FAIL with `ModuleNotFoundError`.

- [ ] **Step 5: Write the module**

Create `src/crawler/sources/art_space_j.py`:

```python
"""Art Space J / 아트스페이스 J (artspacej.com) — HTML extractor.

Strategy (recon 2026-06-04):
A photography-only space ("SPACE FOR PHOTO") in Seongnam, heavy on solo shows.
The site is self-built PHP; its HTTPS root WAF-returns 406 and the cert is
self-signed, so we use the **http** ``/sub/*.php`` board paths with a browser
UA. We crawl current (``sub03_01.php``) + upcoming (``sub03_03.php``). Each list
row is ``[CUBE1]작가 개인전_부제_2026.03.06-04.30`` with a separate
``2026.03.06 ~ 2026.04.30`` date and a ``mode=view&idx=<n>`` detail href. Detail
pages expose no og:image, so the poster comes from the ``/uploaded/board/exhib``
image in the body.
"""

from __future__ import annotations

import re
import time
import urllib.parse
from collections.abc import Iterable

import httpx
from selectolax.parser import HTMLParser
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

from crawler.models import RawExhibition, SourceName
from crawler.normalize.text import clean_whitespace
from crawler.sources._detail import extract_date_range, meta_description, paragraphs_text
from crawler.sources.base import register_source

_BASE_URL = "http://www.artspacej.com"
_LIST_URLS = (
    f"{_BASE_URL}/sub/sub03_01.php?boardid=exhib",  # current
    f"{_BASE_URL}/sub/sub03_03.php?boardid=exhib",  # upcoming
)
_USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Safari/537.36"
)

_VENUE_NAME = "Art Space J"
_VENUE_REGION = "성남"
_VENUE_ADDRESS = "경기도 성남시 분당구 정자일로 248 파크뷰 D상가 2층"

_VIEW_HREF_RE = re.compile(r"mode=view")
_ROOM_TAG_RE = re.compile(r"^\s*\[[^\]]+\]\s*")  # leading [CUBE1] etc.
_TRAILING_DATE_RE = re.compile(r"_?\s*\d{4}\s*\.\s*\d{1,2}\s*\.\s*\d{1,2}.*$")


def _clean_title(text: str) -> str:
    """Strip a leading ``[CUBE1]`` room tag and a trailing date token."""
    t = _ROOM_TAG_RE.sub("", text)
    t = _TRAILING_DATE_RE.sub("", t)
    return clean_whitespace(t).rstrip("_ ")


def _parse_list(html: str) -> list[dict]:
    doc = HTMLParser(html)
    items: list[dict] = []
    seen: set[str] = set()
    for a in doc.css("a"):
        href = a.attributes.get("href") or ""
        if not _VIEW_HREF_RE.search(href):
            continue
        url = urllib.parse.urljoin(_BASE_URL + "/sub/", href)
        if url in seen:
            continue
        text = clean_whitespace(a.text())
        row = a.parent
        row_text = clean_whitespace(row.text()) if row is not None else text
        source = text if text else row_text
        title = _clean_title(source)
        if not title:
            continue
        seen.add(url)
        date_range = extract_date_range(source) or extract_date_range(row_text)
        items.append({"source_url": url, "title": title, "date_range": date_range})
    return items


def _parse_detail(html: str) -> dict:
    doc = HTMLParser(html)
    poster = None
    for img in doc.css("img"):
        src = img.attributes.get("src") or ""
        if "uploaded/board/exhib" in src:
            poster = urllib.parse.urljoin(_BASE_URL, src)
            break
    body = doc.css_first("body")
    description = (paragraphs_text(body) if body is not None else None) or meta_description(doc)
    return {"poster_image_url": poster, "description": description}


class ArtSpaceJExtractor:
    name = SourceName.ART_SPACE_J
    country = "KR"

    def __init__(self, delay_s: float = 1.0, timeout_s: float = 30.0) -> None:
        self.delay_s = delay_s
        self._client = httpx.Client(
            timeout=timeout_s,
            headers={
                "User-Agent": _USER_AGENT,
                "Accept-Language": "ko,en-US;q=0.8,en;q=0.7",
            },
            follow_redirects=True,
            verify=False,  # self-signed cert; we use http but guard https redirects
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
        for list_url in _LIST_URLS:
            try:
                items = _parse_list(self._get(list_url))
            except Exception:  # noqa: BLE001 — one board failing shouldn't abort
                items = []
            for item in items:
                if item["source_url"] in seen:
                    continue
                seen.add(item["source_url"])
                try:
                    detail = _parse_detail(self._get(item["source_url"]))
                except Exception:  # noqa: BLE001
                    detail = {"poster_image_url": None, "description": None}
                raw = {
                    "title": item["title"],
                    "category": "사진",
                    "date_range": item["date_range"],
                    "venue_name": _VENUE_NAME,
                    "venue_region": _VENUE_REGION,
                    "venue_address": _VENUE_ADDRESS,
                    "poster_image_url": detail["poster_image_url"],
                    "description": detail["description"],
                    "artists": [],
                }
                yield RawExhibition(
                    source=SourceName.ART_SPACE_J,
                    source_url=item["source_url"],
                    raw=raw,
                )
                if self.delay_s > 0:
                    time.sleep(self.delay_s)


register_source(SourceName.ART_SPACE_J, ArtSpaceJExtractor)
```

> **Note on `verify=False`:** ruff may flag `S501`. The repo already accepts http-only sources (`gallery_bresson`); we use http URLs here and `verify=False` only guards an accidental https redirect. If `ruff check` flags it, add `# noqa: S501` on that line (matching the project's pragmatic style).

- [ ] **Step 6: Register the module**

In `src/crawler/sources/__init__.py`, add `art_space_j,  # noqa: F401` (alphabetical: after `artmap,`).

- [ ] **Step 7: Run the test to verify it passes**

Run: `pytest tests/sources/test_art_space_j.py -q`
Expected: PASS. If `_parse_list` misses rows, the list anchors may not carry the title text directly — read title from `row_text` instead of `text`. If the poster isn't found, confirm the image path substring against `detail.html`.

- [ ] **Step 8: Lint + full suite**

Run: `ruff check src/ tests/ && pytest -q`
Expected: PASS.

- [ ] **Step 9: Commit**

```bash
git add src/crawler/sources/art_space_j.py src/crawler/models.py src/crawler/sources/__init__.py tests/sources/test_art_space_j.py tests/fixtures/art_space_j/
git commit -m "feat(sources): add Art Space J (artspacej.com) photo source"
```

---

## Task 5: Live smoke-test all four sources (no writes)

**Files:** none (manual verification).

- [ ] **Step 1: Dry-run each source against the live sites**

Run each and confirm real exhibitions print as normalized JSON (titles, dates, posters look sane):

```bash
crawler dry-run place_m
crawler dry-run totem_pole
crawler dry-run gallery_tosei
crawler dry-run art_space_j
```
Expected: each prints ≥1 exhibition with `medium` classified as `photo`, plausible `date_range`, and a poster URL where available. If any source prints 0 or garbage, revisit that source's `_parse_list` against its fixture (the parsers use robust text/regex matching, but live markup is the source of truth).

- [ ] **Step 2: Update the source-expansion memory**

Append the 4 shipped verdicts (status ✅ DONE, URL pattern, gotchas: Place M no-og, TPPG homepage SSR, Tosei Shift_JIS+http, Art Space J self-signed+http) to the `project-source-expansion` memory so they aren't re-investigated.

- [ ] **Step 3: Final commit if anything changed**

```bash
git add -A && git commit -m "chore: verify 4 new photo sources via dry-run" || echo "nothing to commit"
```

---

## Self-Review (completed during planning)

- **Spec coverage:** All 4 spec sources (place_m, totem_pole, gallery_tosei, art_space_j) each have a full TDD task. Common-pattern requirements (per-file module, register_source, enum, __init__ import, photo category seed, shared/source-local date helpers, fixture TDD) are encoded in every task. Excluded candidates are documented in the spec, not the plan (correctly out of scope).
- **Placeholder scan:** No TBD/TODO; every code step ships complete module/test code. The one unavoidable runtime dependency — capturing live HTML — is an explicit Step 1 per task with the exact `curl` command, and each task flags the single spot to reconcile against the fixture.
- **Type consistency:** `SourceName` members (`PLACE_M`, `TOTEM_POLE`, `GALLERY_TOSEI`, `ART_SPACE_J`) match between models.py edits, module `name`/`register_source`, and tests. Function names (`_parse_list`, `_parse_detail`, `_extract_jp_date_range`, `_clean_title`) are consistent between each module and its test imports. `raw` dict keys match the existing pgi/zen_foto/gallery_bresson shape.
