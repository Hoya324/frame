# Artmap (art-map.co.kr) — extraction notes

## URLs
- List page (browser): `https://art-map.co.kr/exhibition/new_list.php` — loads an empty shell.
  Cards are injected by JavaScript via AJAX. Do NOT scrape this URL.
- **Data endpoint (real source)**: POST `https://art-map.co.kr/data/new_exhibition.php`
  - Verified via fixture capture 2026-05-28.
  - `type=ing` ongoing, `type=exp` upcoming, `type=end` past
- Detail: `https://art-map.co.kr/exhibition/view.php?idx=<id>`

## Data endpoint parameters (POST form body)
- `start` — offset counter, increments by 4 each batch (0, 4, 8, …)
- `wrap` — batch number, increments by 1 each batch (1, 2, 3, …)
- `type` — exhibition status (`ing`, `exp`, `end`)
- `area` — region filter (0 = all)
- `cate` — genre filter (empty = all)
- `od` — sort order (2 = popularity)
- `v_cnt` — visitor count state (0 initially)
- `online` — online exhibitions filter (0 = no)

## Card HTML structure (verified against `tests/fixtures/artmap/list_page_1.html`)
Each batch response contains multiple `<div style='...' ...><a href='view.php?idx=NNNN'>...</a></div>` cards.

Inside each `<a>`:
- `<img src='https://art-map.co.kr/art-map/public/upload/...'>` — absolute poster URL
- `<div class='new_exh_list'>` containing:
  - `<span id='ttl_N'>` — **title** (NOT `<h3>` or `<h4>`)
  - `<span>` (2nd) — venue/region combined: `"서울시립미술관서소문본관/서울"` (split on `/`)
  - `<span>` (3rd) — date range: `"2026.05.19 ~ 2026.10.25"`
  - `<span class='mck'>` — map checkbox (hidden, ignore)

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
- Walk batches: start=0/wrap=1, start=4/wrap=2, start=8/wrap=3, …
- Stop when response returns "end" string or zero cards.
- Cap at 20 batches for v1 (~80 exhibitions max per run; tune as needed).
- Dedup by source_url to handle any overlaps.

## Known quirks
- Dates sometimes show `2026.05.19 ~ 미정` — start parses, end is None.
- Some cards have no poster image (use null).
- `구분` field is missing on roughly half of older entries — default to `기획전`.
- The `href` on card `<a>` elements is relative (`view.php?idx=N`) — prepend `https://art-map.co.kr/exhibition/`.
