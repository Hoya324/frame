# 국립현대미술관 (MMCA) — mmca.go.kr

Recon date: 2026-07-20 (verified live).

## Endpoint

The public list page `/exhibitions/progressList.do` is an empty shell whose
cards are rendered client-side by jQuery. The data source is a clean JSON
endpoint that works with a plain GET:

```
GET https://www.mmca.go.kr/exhibitions/AjaxExhibitionList.do
  ?exhFlag=1            # 1 = ongoing, 2 = upcoming, 3 = past (~1,300 rows)
  &pageIndex=1          # 1-based; 8 records/page
  &searchExhPlaCd=      # branch filter (empty = all)
  &searchExhCd=         # genre filter (empty = all)
  &sort=1
```

Response shape: `{ paginationInfo: { totalPageCount, totalRecordCount, ... },
exhibitionsList: [ ...records ] }`. We crawl `exhFlag=1` and `2`, walking
`pageIndex` until `totalPageCount`.

## Record fields (all needed data is in the list JSON — no detail fetch)

| field | meaning | example |
|---|---|---|
| `exhId` | stable id, keys the detail URL | `202601060002026` |
| `exhTitle` | title | `MMCA×LG OLED 시리즈 2026` |
| `exhStDt` / `exhEdDt` | ISO date range | `2026-07-24` / `2026-08-02` |
| `exhPlaNm` | branch: 서울/과천/덕수궁/청주/어린이미술관 | `서울` |
| `exhPlaDtl` | room detail | `지하1층, MMCA영상관` |
| `exhArtist` | names, or headcount ("9인", "… 등 40여 명"), or `-` | `장 클로드 루소` |
| `exhAdm` | admission free text; `0` = free, `-` = unspecified | `과천관통합권 3,000원` |
| `exhThumbImg` | site-relative poster path | `/upload/exhibition/...png` |
| `exhCd` / `exhTpCd` | museum's own genre code — includes `필름앤비디오` | `필름앤비디오` |
| `exhThemewd` | comma-separated theme keywords | `실험 영화,프레임,응시` |
| `exhContentsSumm` | curated one-line summary | |
| `exhContents` | full HTML body | |

## Detail URL

Site JS submits a POST form (`fn_Detail`), but plain GET renders the same
page and is used as `source_url`:

```
https://www.mmca.go.kr/exhibitions/exhibitionsDetail.do?exhFlag={flag}&exhId={exhId}
```

## Filtering

MMCA is a general art museum — most shows are painting/sculpture. Records
pass the shared photo/film/media gate (`crawler.sources._media.media_category`)
with the curated short fields (title + exhCd/exhTpCd + exhThemewd +
exhContentsSumm) on the broad tier and the HTML body on the strict tier.
On the recon date, 20 live records (13 ongoing + 7 upcoming) yielded exactly
2 media shows (실험영화 회고전, 미디어 설치) — low yield is expected and
correct.

## Quirks

- `exhAdm` mixes free-text: `0` → free, `-` → unspecified, otherwise often
  carries a `N,NNN원` amount (seeds `price_min`/`price_max`).
- `exhArtist` may be a bare headcount (`9인`) or end in `… 등 40여 명`; both
  handled by `_parse_artists`.
- 어린이미술관 branch is physically inside the 과천 campus — mapped to the
  과천 address.
- The endpoint answers without Referer/X-Requested-With, but we send a
  Referer anyway to blend in with the site's own AJAX traffic.
