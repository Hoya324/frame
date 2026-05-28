# 뮤지엄한미 (Museum Hanmi, museumhanmi.or.kr) — extraction notes

## Background
Korea's oldest dedicated photography museum, established 2002. Has two physical branches
in Samcheong-dong, Seoul, treated as separate venues in the resolver:
- **삼청** — main branch
- **삼청별관** — annex (별관)

Annual exhibition volume: ~6 per year across both branches.

## URLs
- **List page**: `https://museumhanmi.or.kr/exhibition/?pgs=<N>` (1-indexed)
  - Page 1: `?pgs=1`
  - Stop when a page returns no `<a class="item row gap-1r">` elements.
- **Detail page**: `https://museumhanmi.or.kr/post_exhibition/<slug>/`
  - WordPress-style permalink (slug is URL-encoded Korean title)

Verified 2026-05-28: `/exhibition/` returns 200 with server-rendered cards.
`/exhibition/?pgs=2` returns 200 with no cards (past exhibitions page was empty).

## Card HTML structure (verified against `tests/fixtures/museum_hanmi/list_page_1.html`)

```html
<a href="https://museumhanmi.or.kr/post_exhibition/<slug>/" class="item row gap-1r">
  <div class="thumb">
    <img src="https://museumhanmi.or.kr/wp-content/uploads/..." />
  </div>
  <div class="meta row gap-16">
    <div class="stat">
      <h6 class="bold">삼청</h6>         <!-- branch → venue_name -->
      <h6 class="bold">진행중</h6>        <!-- status text, not extracted -->
    </div>
    <h4>《전시 제목》</h4>               <!-- title -->
    <h6 class="text-sub single-line">YYYY.MM.DD. 요일 ~ YYYY.MM.DD. 요일</h6>
  </div>
</a>
```

## Date format quirk
Museum Hanmi uses `"2026.05.22. 금 ~ 2026.09.30. 수"` (trailing dot after day,
then Korean weekday abbreviation). This format required a fix to
`src/crawler/normalize/dates.py` — added `_COMPACT_DATE_PATTERN` to strip the
weekday suffix before passing to dateutil. Committed as
`fix(normalize): parse dates with Korean weekday suffix`.

## Selectors
| Field | Selector |
|---|---|
| Card container | `a.item.row.gap-1r` |
| Link (source_url) | `href` attribute on container |
| Poster image | `img` (first, inside `.thumb`) |
| Venue/branch | `h6.bold` (first in `.stat`) |
| Title | `h4` |
| Date range | `h6.text-sub` |

## Pagination strategy
- Walk pages: `?pgs=1`, `?pgs=2`, …
- Stop when a page has zero `a.item.row.gap-1r` elements.
- Cap at 20 pages for v1.

## Robots & manners
- 1-second delay between requests (default).
- User-Agent: `PhotoExhibitionCrawler/0.1 (+contact@example.com)`.
- No `robots.txt` disallow found for `/exhibition/` path.

## Known quirks
- Only 2 exhibitions were live on 2026-05-28 (single-page list).
- Slug is URL-percent-encoded Korean text (e.g. `%e3%80%8a...%e3%80%8b`).
- Image URLs may contain Korean characters (not percent-encoded in `src`).
- `venue_name` is always one of `["삼청", "삼청별관"]` — resolver uses this
  to distinguish the two branches as separate venue entities.
