# SeMA 통합 (서울시립미술관 전 분관, sema.seoul.go.kr) — extraction notes

Verified 2026-07-20.

## Scope

All SeMA branches in one crawl — 서소문본관, 북서울, 남서울, 서서울,
미술아카이브, 백남준을 기억하는 집, 난지미술창작스튜디오, plus off-site shows
(e.g. 주워싱턴한국문화원) — **EXCEPT 서울시립 사진미술관**, which the dedicated
`photo_sema` source already crawls (branch filter `exPlace=ORG51`). Cards whose
venue text contains `사진미술관` are skipped here to avoid duplicate rows.

SeMA is a general art museum, so every card passes the shared photo/film/media
keyword gate (`crawler/sources/_media.py`): broad keywords over title + venue
text, strict compounds over the detail description. Expect 1-3 yields per run.

## URLs

- **List page**: GET `https://sema.seoul.go.kr/kr/whatson/landing?whatsonMenuDivList=EX&whenType=FROM_TODAY`
  - No `exPlace` parameter → all branches.
  - `whenType=FROM_TODAY` returns current + upcoming exhibitions.
- **Pagination**: append `&currentPage=N` for pages 2, 3, … (1-based).
- **Detail page**: `https://sema.seoul.go.kr/kr/whatson/exhibition/detail?exNo=<IDX>`
  - `IDX` is the `data-idx` attribute on the card `<div>`.

### Gotchas (from photo_sema recon, re-verified 2026-07-20)

- `/kr/whatson/exhibition`, `/kr/whatson`, `/ex/currEx` → **HTTP 500**. The
  landing URL above is the only working list endpoint.
- Recon notes mentioned a `data-ex-enddt="YYYYMMDD"` card attribute; the live
  cards do **not** carry it (not needed — `span.o_h3` has the full range).

## Card HTML structure

Same markup as photo_sema (see `docs/sources/photo_sema.md` for the full
snippet):

- `div.viewLink[data-idx]` → card; `data-idx` → detail URL `?exNo=<IDX>`
- `data-ex-menu-div="EXM01"` → standard exhibition (skip `EOM01` outdoor
  sculpture cards etc.)
- `strong.o_h1` → title
- `span.o_h2.epEcPlaceNm` → venue text (blank child spans; trailing comma to
  strip), e.g. `서울시립 북서울미술관`
- `span.o_h3` → date range `YYYY/MM/DD~YYYY/MM/DD` (kept native — parses fine
  downstream)
- `img[src]` → poster (relative `/common/imgFileView?FILE_ID=N` — prepend
  `https://sema.seoul.go.kr`)

`venue_name` = the card's venue text; `venue_region` = `서울` (all SeMA
branches are in Seoul; the geocoder resolves the address from name + region,
so no per-branch address table).

## Detail page

Description prose in `div.o_body` (`paragraphs_text`), meta-description
fallback — identical to photo_sema. The detail is fetched **before** the media
gate so the strict compound tier can see the description; a failed detail
fetch degrades to gating on title + venue alone (crawl never aborts).

## Pagination strategy

- GET page 1 (no `currentPage`), then `&currentPage=2`, …
- **Stop signal**: past the last page the server still renders one EMPTY
  `div.viewLink` template **without** `data-idx` — stop when no div carries a
  `data-idx`, not when `div.viewLink` disappears.
- Post-filter card count must NOT end pagination (a page holding only
  EOM01 / 사진미술관 / non-media cards is not the last page).

## Exhibition count (2026-07-20 snapshot)

- Page 1: 12 EXM01 cards (1 at 사진미술관 → excluded → 11 pre-gate).
- Page 2: 7 EXM01 + 3 EOM01 cards; page 3+: empty template.
- Media-gate survivors from the list text alone: 1
  (서서울미술관 미디어 소장품전 《서서울의 투명한 |청소년| 기계》); the
  detail-description strict tier can promote a few more.

## Robots & manners

- No robots.txt restriction found; public museum run by Seoul Metropolitan
  Government.
- 1-second delay between requests; Chrome desktop User-Agent.
