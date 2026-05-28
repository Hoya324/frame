# Photo SeMA (서울시립 사진미술관) — extraction notes

Verified 2026-05-28.

## URLs

- **List page**: GET `https://sema.seoul.go.kr/kr/whatson/landing?whatsonMenuDivList=EX&exPlace=ORG51&whatChoice2=N&whatChoice3=N&whatChoice4=N&whatChoice5=N&whenType=FROM_TODAY`
  - `exPlace=ORG51` pre-filters to Photo SeMA branch on the server side.
  - `whenType=FROM_TODAY` returns current and upcoming exhibitions.
  - Other `whenType` values: `PLAN_DAY` (upcoming only), `PAST_DAY` (past).
- **Pagination**: append `&currentPage=N` for pages 2, 3, … (1-based). Page 1 omits the parameter.
- **Detail page**: `https://sema.seoul.go.kr/kr/whatson/exhibition/detail?exNo=<IDX>`
  - `IDX` is the `data-idx` attribute on the card's `<div>` element.

### Reconnaissance (2026-05-28)

| URL | Status |
|---|---|
| `sema.seoul.go.kr/kr/whatson/exhibition` | 500 |
| `sema.seoul.go.kr/kr/whatson/exhibition/list` | 500 |
| `sema.seoul.go.kr/kr/whatson/exhibition_index` | 500 |
| `sema.seoul.go.kr/kr/whatson` | 500 |
| `sema.seoul.go.kr/kr/` | 500 |
| `sema.seoul.go.kr/kr/visit/photosema` | **200** |
| `sema.seoul.go.kr/kr/whatson/landing` | **200** |
| `sema.seoul.go.kr/kr/whatson/landing?...&exPlace=ORG51&...` | **200** ← chosen |

The landing page with `exPlace=ORG51` is the working list URL. It returns server-rendered HTML with exhibition cards directly (no JavaScript injection required).

## Branch codes (SeMA internal)

| Code | Branch |
|---|---|
| ORG60 | 서울시립미술관 (전체) |
| ORG01 | 서울시립미술관 서소문본관 |
| ORG08 | 서울시립 북서울미술관 |
| ORG50 | 서울시립 서서울미술관 |
| ORG03 | 서울시립 남서울미술관 |
| **ORG51** | **서울시립 사진미술관 ← this extractor** |
| ORG04 | 난지미술창작스튜디오 |
| ORG12 | SeMA 벙커 |
| ORG11 | SeMA 창고 |
| ORG10 | SeMA 백남준기념관 |
| ORG61 | 서울시립 서서울미술관 관련시설 |

## Card HTML structure

```html
<div id="dv_<IDX>" class="pure-u-1-2 pure-u-md-1-4 viewLink app-u-1"
     data-idx="<IDX>" data-whatson-menu-div="EX" data-ex-menu-div="EXM01"
     style="padding:0px 25px 0px 25px;">
  <a href="javascript:;" class="o_figure">
    <div class="o_thumb">
      <img src="/common/imgFileView?FILE_ID=<FILE_ID>" .../>
    </div>
    <div class="t-metadata o_figcaption">
      <strong class="o_h1">TITLE</strong>
      <span class="o_h2 app-none">
        <span class="ico-ex">전시</span>
      </span>
      <span class="o_h2 epEcPlaceNm app-none">
        <!-- many blank sibling spans, one non-blank with venue text -->
        서울시립 사진미술관,
      </span>
      <span class="o_h3">
        2026/04/09~2026/06/14
      </span>
    </div>
  </a>
</div>
```

Key extraction points:
- `data-idx` on the `<div>` → detail URL `?exNo=<IDX>`
- `data-ex-menu-div="EXM01"` → standard exhibition (skip biennale `EBM01`, festival `EPF01`, outdoor `EOM01`)
- `<strong class="o_h1">` → title
- `<span class="o_h2 epEcPlaceNm app-none">` → venue text (has trailing comma — strip it)
- `<span class="o_h3">` → date range in `YYYY/MM/DD~YYYY/MM/DD` format
- `<img src="...">` → poster image (relative path; prepend `https://sema.seoul.go.kr`)

## Branch filter strategy

Two-layer filtering is applied:
1. **URL-level**: `exPlace=ORG51` tells the server to return only Photo SeMA exhibitions.
2. **Parser-level** (defensive): each card's venue text is checked for the substring `사진미술관`. Cards without this substring are skipped. This guards against the server returning mixed results or a URL parameter being ignored.

## Pagination strategy

- GET page 1 (no `currentPage` param), then page 2 (`&currentPage=2`), etc.
- Stop when the response HTML contains no `div.viewLink` cards.
- Cap at `max_pages=10` for v1 (Photo SeMA opened April 2026 and typically has <30 active exhibitions).

## Exhibition count (2026-05-28 snapshot)

- Total cards on all-branch landing page: 12 (2 pages × ~6)
- Photo SeMA cards (`exPlace=ORG51`): **2** (all fit on page 1)
- Photo SeMA is newly reopened (April 2026); exhibition count will grow.

## Robots & manners

- `robots.txt` not found at sema.seoul.go.kr. The site is a public museum run by Seoul Metropolitan Government. Crawling the public exhibition list is acceptable.
- 1-second delay between page requests.
- User-Agent: `PhotoExhibitionCrawler/0.1 (+contact@example.com)`

## Known quirks

- Many empty `<span>` siblings inside `.epEcPlaceNm` — use `.text(strip=True)` on the parent to get the combined text; the trailing comma must be stripped.
- Card links use `javascript:;` — detail URL is constructed from `data-idx`, not the `href`.
- Image URLs are relative (`/common/imgFileView?FILE_ID=N`) — prepend `https://sema.seoul.go.kr`.
- The `whenType=FROM_TODAY` parameter shows current+upcoming. To get past exhibitions, change to `PAST_DAY` (separate crawl run, not implemented in v1).
