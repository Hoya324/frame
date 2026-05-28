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
