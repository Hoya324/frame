# M3 — Additional P0 Sources Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add the 4 remaining P0 sources (Naver 전시 search, Photo SeMA, 뮤지엄한미, KOBA) following the Artmap pattern established in M1+M2.

**Architecture:** Same pipeline as M1+M2. Each source is a self-contained `src/crawler/sources/<name>.py` module that yields `RawExhibition` objects, registers itself via `register_source()`, and is auto-imported by `src/crawler/sources/__init__.py`. Each source has a fixture-based unit test.

**Tech Stack:** Same as M1+M2 (httpx + selectolax). **If a site is genuinely JS-only (SPA with no server-rendered fallback and no public data endpoint), the implementer should report `BLOCKED` rather than introducing Playwright in this plan.** Playwright addition is its own decision and belongs in a separate plan.

**Spec reference:** `docs/superpowers/specs/2026-05-28-photo-exhibition-crawler-design.md` §2 (sources).

**Reference implementation:** `src/crawler/sources/artmap.py` is the canonical model. Read it before starting.

**Out of scope:**
- GitHub Actions `crawl.yml` and `healthcheck` workflow (M4)
- popularity scoring (v1.5)
- detail-page enrichment (v1.5)

---

## Pre-flight reconnaissance summary

Each implementer task starts with a **reconnaissance step** — fetch the site, decide which approach works (static HTML, partial API call, or BLOCKED). Below is the summary of controller-side recon to give implementers a starting point. **Treat these as hints, not facts** — verify with your own fetch first.

| Site | Recon result | Likely approach |
|---|---|---|
| Naver 전시 검색 | WebFetch blocked (403/UA gating expected) | Try mobile endpoint `m.search.naver.com` or different User-Agent. If still blocked → BLOCKED. |
| Photo SeMA | Initial URL returned 500 | Find correct URL via `sema.seoul.go.kr` home. Likely `/kr/whatson/exhibition/list` or similar. |
| 뮤지엄한미 | Carousel slide format on home; per-exhibit pages at `/post_exhibition/` | Look for a real list page (`/exhibition/`, `/exhibitions/`, or sitemap). The carousel itself may be enough if it renders server-side. |
| KOBA | Mostly SPA (WebFetch got only title) | Check if event/conference info is embedded server-side at `kobashow.com/event` or `/exhibition`. If pure SPA → BLOCKED. |

---

## File Structure

Files this plan will create/modify:

```
photo-exhibition-crawler/
├── src/crawler/sources/
│   ├── __init__.py                  ← Modify (add imports)
│   ├── naver.py                     ← Create (Task 1)
│   ├── photo_sema.py                ← Create (Task 2)
│   ├── museum_hanmi.py              ← Create (Task 3)
│   └── koba.py                      ← Create (Task 4)
├── tests/
│   ├── fixtures/
│   │   ├── naver/                   ← Create (Task 1)
│   │   ├── photo_sema/              ← Create (Task 2)
│   │   ├── museum_hanmi/            ← Create (Task 3)
│   │   └── koba/                    ← Create (Task 4)
│   ├── sources/
│   │   ├── test_naver.py            ← Create (Task 1)
│   │   ├── test_photo_sema.py       ← Create (Task 2)
│   │   ├── test_museum_hanmi.py     ← Create (Task 3)
│   │   └── test_koba.py             ← Create (Task 4)
│   └── integration/
│       └── test_run_all_smoke.py    ← Create (Task 5)
└── docs/sources/
    ├── naver.md                     ← Create (Task 1)
    ├── photo_sema.md                ← Create (Task 2)
    ├── museum_hanmi.md              ← Create (Task 3)
    └── koba.md                      ← Create (Task 4)
```

Each source module is independent. Failure to ship one source doesn't block the others.

---

## Common Task Template

Each source task follows this exact pattern. The differences are: site URL, HTTP method, response shape, selectors. Use `src/crawler/sources/artmap.py` and `tests/sources/test_artmap.py` as your reference.

**For every site task you do:**

1. **Reconnaissance** — fetch the site manually, identify the working list endpoint and selector strategy. If blocked or pure-SPA, stop and report BLOCKED.
2. **Notes** — write `docs/sources/<name>.md` with URL pattern, pagination, selectors, quirks, robots/manners.
3. **Fixture** — capture one real list-page response into `tests/fixtures/<name>/list_page_1.<html|json>`.
4. **Expected** — author `tests/fixtures/<name>/expected.jsonl` for the first 3 cards (or fewer if the page has fewer).
5. **Test** — write a failing unit test in `tests/sources/test_<name>.py` modeled on `tests/sources/test_artmap.py`.
6. **Extractor** — implement `src/crawler/sources/<name>.py` with a class that has `name: SourceName`, `crawl() -> Iterable[RawExhibition]`, and calls `register_source(...)` at module bottom.
7. **Green** — run `.venv/bin/pytest tests/sources/test_<name>.py -v` and verify pass.
8. **Commit** as a self-contained change.

**Naming conventions:**
- Class: `<Name>Extractor` (e.g., `NaverExtractor`, `PhotoSemaExtractor`, `MuseumHanmiExtractor`, `KobaExtractor`)
- `SourceName` enum values already exist: `NAVER`, `PHOTO_SEMA`, `MUSEUM_HANMI`, `KOBA`

---

## Task 1: Naver 전시 검색

**Files:**
- Create: `docs/sources/naver.md`
- Create: `tests/fixtures/naver/list_page_1.html` (real capture)
- Create: `tests/fixtures/naver/expected.jsonl` (3 entries)
- Create: `tests/sources/test_naver.py`
- Create: `src/crawler/sources/naver.py`

- [ ] **Step 1.1: Reconnaissance**

Try these URLs in order. First one that returns a non-empty HTML body with exhibition cards wins:

```bash
# Desktop integrated search
curl -sSL -A "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36" \
  "https://search.naver.com/search.naver?where=nexearch&query=%EC%82%AC%EC%A7%84+%EC%A0%84%EC%8B%9C" \
  -o /tmp/naver_desktop.html
wc -c /tmp/naver_desktop.html

# Mobile search (often less restricted)
curl -sSL -A "Mozilla/5.0 (iPhone; CPU iPhone OS 16_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.0 Mobile/15E148 Safari/604.1" \
  "https://m.search.naver.com/search.naver?where=m&query=%EC%82%AC%EC%A7%84+%EC%A0%84%EC%8B%9C" \
  -o /tmp/naver_mobile.html
wc -c /tmp/naver_mobile.html
```

Inspect each file. Look for:
- Card containers (often `<li class="bx ...">` or similar)
- Title, venue, date, image fields
- Pagination links (often `&start=11`, `&start=21`)

**If both fetches return blocked pages, login walls, or contain no exhibition data:** Stop, report status `BLOCKED` with the file contents you saw. The controller will decide whether to add Playwright (separate plan), use a different Naver endpoint, or skip Naver from v1.

- [ ] **Step 1.2: Write `docs/sources/naver.md`**

After successful recon, document URL pattern, pagination (`start` param? `page` param?), selectors for title/venue/date/image, User-Agent requirements, robots/manners, known quirks. Use `docs/sources/artmap.md` as the template structure.

- [ ] **Step 1.3: Save fixture**

```bash
mkdir -p tests/fixtures/naver
cp /tmp/naver_<chosen>.html tests/fixtures/naver/list_page_1.html
head -3 tests/fixtures/naver/list_page_1.html  # sanity check
```

- [ ] **Step 1.4: Write `tests/fixtures/naver/expected.jsonl`**

Based on the first 3 visible exhibition cards in your fixture. Schema:

```json
{"source": "naver", "source_url": "https://...", "raw": {"title": "...", "venue_name": "...", "date_range": "...", "poster_image_url": "..."}}
```

Fields that are genuinely absent in the snapshot: use `null`. Don't fabricate values.

- [ ] **Step 1.5: Write failing test `tests/sources/test_naver.py`**

Model on `tests/sources/test_artmap.py`. Adapt:
- `respx.get(...)` or `respx.post(...)` matching the actual URL pattern Naver uses
- `NaverExtractor(...)` constructor matching what you'll implement
- Same fixture-loading helpers (copy `_load_fixture`, `_load_expected`)
- Same two test functions: (a) parses first three cards, (b) stops when page empty

- [ ] **Step 1.6: Run failing test**

```bash
.venv/bin/pytest tests/sources/test_naver.py -v
```

Expected: ImportError on `crawler.sources.naver`.

- [ ] **Step 1.7: Implement `src/crawler/sources/naver.py`**

Use `src/crawler/sources/artmap.py` as your structural template. Adapt to Naver's URL, HTTP method, response shape, selectors. Required surface:

```python
class NaverExtractor:
    name = SourceName.NAVER
    def __init__(self, max_pages: int = 10, delay_s: float = 1.0, timeout_s: float = 20.0) -> None: ...
    def crawl(self) -> Iterable[RawExhibition]: ...
# register at module bottom:
register_source(SourceName.NAVER, NaverExtractor)
```

Use `httpx.Client` with the User-Agent you found that works in recon. Add `@retry` decorator on the HTTP method like Artmap does. Use selectolax to parse HTML.

- [ ] **Step 1.8: Run test, expect pass**

```bash
.venv/bin/pytest tests/sources/test_naver.py -v
```

Expected: 2 passed.

If a field is `None` where you expected a value → fix `_extract_cards`, don't loosen the test.

- [ ] **Step 1.9: Commit**

```bash
git add src/crawler/sources/naver.py tests/sources/test_naver.py tests/fixtures/naver/ docs/sources/naver.md
git commit -m "feat(sources): Naver exhibition search extractor with fixture-based tests"
```

---

## Task 2: Photo SeMA (서울시립 사진미술관)

**Files:**
- Create: `docs/sources/photo_sema.md`
- Create: `tests/fixtures/photo_sema/list_page_1.html`
- Create: `tests/fixtures/photo_sema/expected.jsonl`
- Create: `tests/sources/test_photo_sema.py`
- Create: `src/crawler/sources/photo_sema.py`

- [ ] **Step 2.1: Reconnaissance**

The initial URL `sema.seoul.go.kr/kr/whatson/exhibition` returned 500. Try alternatives:

```bash
UA='Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36'

# Home page first — find the correct exhibition link
curl -sSL -A "$UA" "https://sema.seoul.go.kr/kr/" -o /tmp/sema_home.html
grep -oE 'href="[^"]*exhibition[^"]*"' /tmp/sema_home.html | head -10
grep -oE 'href="[^"]*whatson[^"]*"' /tmp/sema_home.html | head -10

# Try common alternates
for url in \
  "https://sema.seoul.go.kr/kr/whatson/exhibition/list" \
  "https://sema.seoul.go.kr/kr/whatson/exhibition_index" \
  "https://sema.seoul.go.kr/kr/whatson" \
  "https://sema.seoul.go.kr/kr/visit/photosema"
do
  echo "=== $url ==="
  curl -s -A "$UA" -o /dev/null -w "%{http_code}\n" "$url"
done
```

Identify the working list page. **Filter for the Photo SeMA branch (사진미술관)** — SeMA runs multiple branches; you want only exhibitions hosted at Photo SeMA. There may be a `?branch=` or `?venue=` query parameter; check.

If you can't find a working list URL or all return 4xx/5xx: report BLOCKED.

- [ ] **Step 2.2: Write `docs/sources/photo_sema.md`**

URL pattern (with branch filter), pagination, selectors, robots/manners, quirks. Note: the branch is "사진미술관" or "Photo SeMA" — different from "서소문본관" or "북서울미술관".

- [ ] **Step 2.3: Save fixture**

```bash
mkdir -p tests/fixtures/photo_sema
curl -sSL -A "$UA" "<working-url>" -o tests/fixtures/photo_sema/list_page_1.html
head -3 tests/fixtures/photo_sema/list_page_1.html
```

- [ ] **Step 2.4: Write `tests/fixtures/photo_sema/expected.jsonl`**

3 entries from the fixture. Each row should have venue_name "서울시립 사진미술관" or similar consistent value (this is what `venue_raw_name` becomes — the resolver merges all Photo SeMA exhibitions under the same venue).

- [ ] **Step 2.5: Write failing test `tests/sources/test_photo_sema.py`**

Same shape as `tests/sources/test_artmap.py`. Two tests: parses three cards + stops on empty.

- [ ] **Step 2.6: Run, expect fail**

```bash
.venv/bin/pytest tests/sources/test_photo_sema.py -v
```

Expected: ImportError on `crawler.sources.photo_sema`.

- [ ] **Step 2.7: Implement `src/crawler/sources/photo_sema.py`**

Same shape as `src/crawler/sources/artmap.py`. Class `PhotoSemaExtractor`, `name = SourceName.PHOTO_SEMA`, `register_source(...)` at bottom.

**Important:** filter at the extractor level — only yield exhibitions hosted at Photo SeMA branch, not SeMA's other branches. If the list page mixes branches, check each card's venue field and skip non-matching ones.

- [ ] **Step 2.8: Run test, expect pass**

```bash
.venv/bin/pytest tests/sources/test_photo_sema.py -v
```

Expected: 2 passed.

- [ ] **Step 2.9: Commit**

```bash
git add src/crawler/sources/photo_sema.py tests/sources/test_photo_sema.py tests/fixtures/photo_sema/ docs/sources/photo_sema.md
git commit -m "feat(sources): Photo SeMA extractor with branch filter"
```

---

## Task 3: 뮤지엄한미 (Museum Hanmi)

**Files:**
- Create: `docs/sources/museum_hanmi.md`
- Create: `tests/fixtures/museum_hanmi/list_page_1.html`
- Create: `tests/fixtures/museum_hanmi/expected.jsonl`
- Create: `tests/sources/test_museum_hanmi.py`
- Create: `src/crawler/sources/museum_hanmi.py`

- [ ] **Step 3.1: Reconnaissance**

Home page used a carousel; look for a real list page:

```bash
UA='Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36'

curl -sSL -A "$UA" "https://museumhanmi.or.kr/" -o /tmp/hanmi_home.html
grep -oE 'href="[^"]*exhibition[^"]*"' /tmp/hanmi_home.html | sort -u
grep -oE 'href="[^"]*전시[^"]*"' /tmp/hanmi_home.html | sort -u

# Common patterns
for url in \
  "https://museumhanmi.or.kr/exhibition/" \
  "https://museumhanmi.or.kr/exhibitions/" \
  "https://museumhanmi.or.kr/exhibition/list" \
  "https://museumhanmi.or.kr/exhibition/current" \
  "https://museumhanmi.or.kr/post_exhibition/" \
  "https://museumhanmi.or.kr/sitemap.xml"
do
  echo "=== $url ==="
  curl -s -A "$UA" -o /dev/null -w "%{http_code}\n" "$url"
done
```

Inspect the most-promising response. The site uses WordPress-style URLs based on `/post_exhibition/`. If there's no list page, the home page's carousel may itself be parseable from the server-rendered HTML — confirm by looking for `<a href="/post_exhibition/...">` links in the home page source.

If carousel content is client-rendered only and no list page exists: report BLOCKED.

- [ ] **Step 3.2: Write `docs/sources/museum_hanmi.md`**

URL pattern, pagination (or "single page, walk per-exhibit links"), selectors, robots/manners.

The site has two branches: "삼청" (main) and "삼청별관" (branch). Capture both via the venue field. **For the purposes of the resolver**, treat them as separate venues — set `venue_name` to whichever branch the exhibition is at.

- [ ] **Step 3.3: Save fixture**

```bash
mkdir -p tests/fixtures/museum_hanmi
curl -sSL -A "$UA" "<working-url>" -o tests/fixtures/museum_hanmi/list_page_1.html
head -3 tests/fixtures/museum_hanmi/list_page_1.html
```

- [ ] **Step 3.4: Write `tests/fixtures/museum_hanmi/expected.jsonl`**

3 entries. Title uses `<h5>` tag, date format `"YYYY. MM. DD. 요일 ~ YYYY. MM. DD. 요일"`. Verify your `crawler.normalize.dates.parse_date_range` handles the dot-and-day format — if not, fix the regex in `src/crawler/normalize/dates.py` and add a unit test case there (in a separate commit).

- [ ] **Step 3.5: Write failing test `tests/sources/test_museum_hanmi.py`**

Same shape as Artmap test. Two tests.

- [ ] **Step 3.6: Run, expect fail**

- [ ] **Step 3.7: Implement `src/crawler/sources/museum_hanmi.py`**

Class `MuseumHanmiExtractor`. The pagination might not be a traditional `page=N` — if it's a single-page carousel, your `crawl()` returns a single batch.

- [ ] **Step 3.8: Run, expect pass**

```bash
.venv/bin/pytest tests/sources/test_museum_hanmi.py -v
```

- [ ] **Step 3.9: Commit**

```bash
git add src/crawler/sources/museum_hanmi.py tests/sources/test_museum_hanmi.py tests/fixtures/museum_hanmi/ docs/sources/museum_hanmi.md
git commit -m "feat(sources): Museum Hanmi extractor with branch awareness"
```

---

## Task 4: KOBA (한국국제방송영상기자재전)

**Files:**
- Create: `docs/sources/koba.md`
- Create: `tests/fixtures/koba/list_page_1.html`
- Create: `tests/fixtures/koba/expected.jsonl`
- Create: `tests/sources/test_koba.py`
- Create: `src/crawler/sources/koba.py`

- [ ] **Step 4.1: Reconnaissance**

KOBA is unusual: it's a single annual trade show, NOT a recurring list of exhibitions. The "extractor" produces one (or very few) `RawExhibition` rows — the current edition and any sub-events (conferences, special zones).

```bash
UA='Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36'

curl -sSL -A "$UA" "https://www.kobashow.com/" -o /tmp/koba_home.html
wc -c /tmp/koba_home.html
grep -oE 'href="[^"]*"' /tmp/koba_home.html | head -20

# Common subpages
for url in \
  "https://www.kobashow.com/event/" \
  "https://www.kobashow.com/overview/" \
  "https://www.kobashow.com/visitor/" \
  "https://www.kobashow.com/exhibitor/" \
  "https://www.kobashow.com/conference/"
do
  echo "=== $url ==="
  curl -s -A "$UA" -o /dev/null -w "%{http_code}\n" "$url"
done
```

If the home is mostly SPA (small file size, no meaningful HTML content), look for server-rendered subpages. The conference / event pages often have static HTML even when the home doesn't.

If everything is client-rendered: report BLOCKED. We can still hardcode the annual KOBA edition as a single curated row in a later task — but not in this plan.

- [ ] **Step 4.2: Write `docs/sources/koba.md`**

URL pattern, parsing strategy (single edition → 1+N rows), how to determine current year's dates and venue. Note the annual cycle.

- [ ] **Step 4.3: Save fixture**

Whichever subpage you found that has the data. May be `/event/` or `/overview/`.

- [ ] **Step 4.4: Write `tests/fixtures/koba/expected.jsonl`**

Typically 1-3 entries: the main KOBA edition + any conference/special-program sub-events. Each entry should have:
- `title`: e.g., "KOBA 2026 — 국제 방송·미디어·음향·조명 전시회"
- `venue_name`: "COEX" (typical) or as parsed
- `date_range`: e.g., "2026.05.12 ~ 2026.05.15"
- `organizer`: "한국전파진흥협회" or as parsed (this is the field that exercises the resolver's Organizer != Venue path)

- [ ] **Step 4.5: Write failing test `tests/sources/test_koba.py`**

Same shape. Tests should be tolerant: KOBA may have only 1 card, so use `assert len(raws) >= 1` instead of `>= 3`.

- [ ] **Step 4.6: Run, expect fail**

- [ ] **Step 4.7: Implement `src/crawler/sources/koba.py`**

`KobaExtractor`. May not need pagination — just one page fetch, parse, yield.

**Set `exhibition_type_text="박람회"` in the raw payload** so the Normalizer classifies it as `ExhibitionType.EXPO`. Set `organizer` to the parsed value so it flows through `NormalizedExhibition.organizer_raw_name` and creates an Organizer row.

- [ ] **Step 4.8: Run, expect pass**

```bash
.venv/bin/pytest tests/sources/test_koba.py -v
```

- [ ] **Step 4.9: Commit**

```bash
git add src/crawler/sources/koba.py tests/sources/test_koba.py tests/fixtures/koba/ docs/sources/koba.md
git commit -m "feat(sources): KOBA expo extractor"
```

---

## Task 5: Wire up registry + end-to-end smoke + README update

**Files:**
- Modify: `src/crawler/sources/__init__.py`
- Create: `tests/integration/test_run_all_smoke.py`
- Modify: `README.md`

- [ ] **Step 5.1: Update `src/crawler/sources/__init__.py`**

Replace existing content with:

```python
"""Source extractors: one module per site.

Importing this package triggers registration of every installed source via the
side-effecting `register_source(...)` call at the bottom of each module.
"""

# Order doesn't matter; we just need each module to be imported.
from crawler.sources import artmap  # noqa: F401
from crawler.sources import naver  # noqa: F401
from crawler.sources import photo_sema  # noqa: F401
from crawler.sources import museum_hanmi  # noqa: F401
from crawler.sources import koba  # noqa: F401
```

**If a Task 1-4 was BLOCKED:** comment out that import with a `# BLOCKED: see <reason>` note so the rest still register.

- [ ] **Step 5.2: Write `tests/integration/test_run_all_smoke.py`**

This test only verifies that all completed extractors register correctly and that `run-all` would invoke them — it doesn't make real HTTP calls.

```python
from crawler.models import SourceName
from crawler.sources.base import all_sources


def test_all_p0_sources_registered():
    """Every P0 source's extractor class is in the registry after package import."""
    registered = all_sources()
    # Adjust expected set based on which tasks completed
    expected = {
        SourceName.ARTMAP,
        SourceName.NAVER,
        SourceName.PHOTO_SEMA,
        SourceName.MUSEUM_HANMI,
        SourceName.KOBA,
    }
    # If a source was BLOCKED in M3, remove it from expected
    # and add a comment explaining why
    assert expected.issubset(set(registered.keys())), \
        f"missing registrations: {expected - set(registered.keys())}"


def test_all_extractors_have_required_interface():
    """Every registered extractor has the expected attributes for the pipeline."""
    for source_name, cls in all_sources().items():
        assert hasattr(cls, "name"), f"{cls.__name__} missing 'name'"
        assert cls.name == source_name, f"{cls.__name__} name mismatch"
        # crawl() exists and is callable on an instance
        instance = cls()
        assert callable(getattr(instance, "crawl", None)), \
            f"{cls.__name__} missing crawl()"
```

- [ ] **Step 5.3: Run smoke test, expect pass**

```bash
.venv/bin/pytest tests/integration/test_run_all_smoke.py -v
```

Expected: 2 passed. If any extractor was BLOCKED in earlier tasks, the assertions in Step 5.2 must reflect that (commented expectations).

- [ ] **Step 5.4: Full suite + lint**

```bash
.venv/bin/pytest -q
.venv/bin/ruff check src/ tests/
```

All green expected.

- [ ] **Step 5.5: Update `README.md`**

In the "## Adding a new source" section (already there), add a line below it summarizing what's available:

Find the existing section and add this block right after it:

```markdown
## Currently supported sources

| Name | Type | Status |
|---|---|---|
| `artmap` | aggregator | ✅ |
| `naver` | aggregator | ✅ (or ⚠️ BLOCKED — note reason) |
| `photo_sema` | museum | ✅ |
| `museum_hanmi` | museum | ✅ |
| `koba` | expo | ✅ |
```

Edit the status markers based on what actually shipped.

- [ ] **Step 5.6: Commit and push**

```bash
git add src/crawler/sources/__init__.py tests/integration/test_run_all_smoke.py README.md
git commit -m "feat(sources): wire up all P0 source registrations + smoke test"
```

---

## Final Verification Checklist

After all 5 tasks (or fewer if some were BLOCKED), confirm:

- [ ] `.venv/bin/pytest -q` — all tests pass
- [ ] `.venv/bin/ruff check src/ tests/` — clean
- [ ] `.venv/bin/crawler --help` — runs
- [ ] `.venv/bin/python -c "from crawler.sources.base import all_sources; print(list(all_sources()))"` — lists every P0 source that was implemented
- [ ] For each successfully-implemented source: `.venv/bin/crawler dry-run <source>` produces JSON output (real HTTP call, but no writes)
- [ ] Git log shows one commit per task

If everything is green and `crawler dry-run <source>` works for at least 3 of the 4 new sources, M3 is complete. BLOCKED sources go into a v1.5 follow-up plan (with Playwright addition decided separately).

## Next plan

M4 — `crawl.yml` GitHub Actions workflow with cron schedule, secrets configuration, `external.yml` for weekly healthcheck, and live sheet integration verification. Plan that as `2026-MM-DD-m4-operations.md` once M3 ships.
