# 아르코미술관 (ARKO Art Center) — arko.or.kr

Recon date: 2026-07-20 (verified live).

## URLs

```
List:   GET https://www.arko.or.kr/artcenter/board/list/506?bid=266
Detail: GET https://www.arko.or.kr/artcenter/board/view/506?bid=266&cid=<CID>
```

**Do NOT use `dateLocation=now`** — the 현재전시 tab is legitimately empty
between shows (it was on recon day: the last show ended 2026-07-19). The
unfiltered board lists every show with machine-formatted dates; we date-filter
in code (keep end ≥ today or future start).

## Selectors

- Card: `ul.researchBoardList > li` — title `span.subject`; labeled `dt/dd`
  pairs in `.textBox .detail dl` (전시기간 "YYYY-MM-DD ~ YYYY-MM-DD", 관람료,
  장소, 작가); thumb `.thum img`.
- `cid` regexed from the href (raw href carries an empty `page=` and
  entity-encoded duplicate `bid` params — rebuild the canonical URL).
- Detail prose: `div.displaySet` (fallback `#tabCon01`, then meta description).

## Quirks

- No pagination at recon time (6 cards, one page; pager block empty).
- Media gate: general contemporary-art venue → `media_category(title, detail
  prose)`. Injectable `today` ctor param keeps tests deterministic.
- Zero yields between media shows is correct behavior.
