# 일민미술관 (Ilmin Museum of Art, ilmin.org) — extraction notes

Verified 2026-07-20.

## Venue

- 일민미술관 / Ilmin Museum of Art — 서울특별시 종로구 세종대로 152 (historic Dong-A Ilbo building, Gwanghwamun).
- General art museum (painting, design, media, photography). **Not** photo-only → every show passes through the shared `_media.media_category` gate.

## URLs

- **List (current shows)**: GET `https://ilmin.org/exhibitions/current/` — server-rendered WordPress/Divi page; the authoritative "currently on" list.
- **Detail**: `https://ilmin.org/exhibition/{slug}/` (singular `exhibition`).
- **Alternative (not used)**: a WP REST list exists at `https://ilmin.org/wp-json/wp/v2/exhibition`, but its items carry **no date range**, so the current page + detail-page approach is preferred.

## List page structure

Cards are Divi `et_pb_code` custom-HTML modules. Each card links to the detail page twice (poster anchor + title anchor), so links are deduped preserving order. The card also carries the date in a
`div.et_pb_code.exhibition_date > div.et_pb_code_inner` block (`2026.6.26.(Fri) ― 2026.8.21.(Fri)`), but we take dates from the detail page instead (single source of truth, same format).

Selector: `a[href]` matching `^https?://ilmin\.org/exhibition/[^/]+/?$`.

## Detail page extraction

| Field | Source |
|---|---|
| title | `og:title`, stripping the trailing ` - 일민미술관` site suffix; fallback `<h1>` |
| date_range | text of `div#main-content` → strip English weekday parens → replace `―` with `~` → `_detail.extract_date_range` |
| description | `paragraphs_text(div#main-content)`; fallback `meta_description` (empty on this site, 2026-07-20) |
| poster_image_url | `og:image` (absolute wp-content URL) |
| artists | `[]` (no stable machine-readable artist field) |

## Date quirks

- Hand-typed span: `2026.6.26.(Fri) ― 2026.8.21.(Fri)`.
  - **Separator is U+2015 HORIZONTAL BAR (`―`)** — NOT covered by `_detail._DATE_RANGE_RE`'s separator class (verified 2026-07-20), so the extractor pre-replaces `―` with `~`.
  - **English weekday parens** (`(Fri)`, also full names) sit between date and separator; stripped by `_EN_WEEKDAY_PAREN_RE` (`(?:mon|tue|wed|thu|fri|sat|sun)[a-z]*` in parens, case-insensitive) — same idea as totem_pole's `(tue)` handling but tolerant of full names.
  - The page repeats the span in shorter forms (`2026.6.26.(금)―8.21.(금)`); the full-form header block comes first in document order and `extract_date_range` takes the first match.

## Media filter

`media_category(title, description)` gates every show; the returned token seeds `raw["category"]`.

2026-07-20 snapshot: exactly **1** current show, 《다시 그린 세계 2026: 순수와 혼종》 (Korean traditional painting / 문인화) → does **not** pass the gate. A live crawl yielding **0 rows (pre-filter count 1)** is correct. Ilmin regularly hosts photo/media shows (e.g. past 사진/뉴미디어 기획전), so the source will produce rows in later cycles.

Note: the 2026-07-20 show is actually staged at the Korean Cultural Centre UK, London (per the page prose), but venue constants stay fixed to 일민미술관 by convention.

## Failure handling

- tenacity retry on `httpx.TransportError` (exp backoff 1→16 s, 3 attempts, reraise).
- A failed/broken detail page skips that card only; the crawl continues.

## Robots & manners

- 1 s delay between detail fetches; desktop-Chrome UA; `follow_redirects=True`.
- Plain curl with the Chrome UA returns 200; no anti-bot observed.
