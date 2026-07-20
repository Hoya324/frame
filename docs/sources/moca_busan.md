# 부산현대미술관 (MOCA Busan) — busan.go.kr/moca

Recon date: 2026-07-20 (verified live).

## URLs

```
Current:  GET https://www.busan.go.kr/moca/exhibition01   (?curPage=N)
Upcoming: GET https://www.busan.go.kr/moca/exhibition02   (?curPage=N)
Detail:   GET https://www.busan.go.kr/moca/exhibition0X/<nttNo>
```

## Selectors

- Card: `ul.thumbListType1 > li > a` — title `strong.tit`; date
  `span.exhibi_datetitle span.date`; thumb `span.thumb img`
  (`/comm/getImage?...&thumbTy=M`).
- Detail (`div.boardView`): labeled `dl.form-data-info` rows (전시시작일 /
  전시종료일 / 참여작가 / 전시장소); prose `dl.form-data-content
  div.se-contents` (SmartEditor, real `<p>` paragraphs).

## Quirks

- Permanent shows read "… ~ 상설", upcoming teasers "2026. ~ 2027." — neither
  parses; `date_range` stays None (cards still yielded if they pass the gate).
  The detail's 전시시작일/종료일 pair recovers full ranges when present.
- 참여작가 may be a headcount blurb ("국외 작가 총 2명(팀)") — filtered.
- Out-of-range `curPage` re-serves page 1 → stop when a page adds nothing new.
- Media gate: `media_category(title, detail prose)`. On recon day the two
  current shows are non-media permanent installations (skipped); upcoming
  "소장품섬_뉴미디어와 미디어" passes on its title.
