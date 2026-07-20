# 국립아시아문화전당 ACC — acc.go.kr (광주)

Recon date: 2026-07-20 (verified live).

## URLs

```
List:   GET https://www.acc.go.kr/main/exhibition.do?PID=0202        (현재전시)
        (&pageIndex=N — out-of-range pages re-serve existing cards)
Detail: GET https://www.acc.go.kr/main/exhibition.do?PID=0202&action=Read&bnkey=EM_<ID>
```

Deviation from initial recon: `contents.do?PID=0202` is a "콘텐츠 준비중"
placeholder — the real server-rendered list is `exhibition.do?PID=0202`.

## Selectors

- Card: `div.skedBoardList li` — title `p.tit` (text node with `<br>`, NOT the
  empty img alt from the first recon pass); curated one-liner `p.cont`; dates
  on the list after all (`p.term`, "YYYY-MM-DD ~ YYYY-MM-DD"); fee `p.price`;
  thumb `div.thumb img`; `bnkey` regexed from href.
- Detail: prose `div.scheduleViewConInfo` (CMS embeds `<style>` blocks —
  decompose style/script first; fallback `p.addTxt`, then og:description);
  labeled `<em>/<span>` rows in `div.detailTxt ul.txtList li` (기간 → canonical
  via `extract_date_range`, 가격); og:image poster fallback.

## Quirks

- Permanent (상설) shows are kept — they carry long explicit ranges.
- Media gate: `media_category(title + list summary, detail prose)`. On recon
  day 12 cards → 3 yields (자밀 프라이즈: 무빙 이미지, 필름앤비디오 아시아의
  장치들, 천일야화의 길 via its media-hall summary).
- Pagination stops when a page adds no new card URLs.
