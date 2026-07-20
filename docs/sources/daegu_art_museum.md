# 대구미술관 (Daegu Art Museum) — daeguartmuseum.or.kr

Recon date: 2026-07-20 (verified live).

**Domain note:** the museum moved to `daeguartmuseum.or.kr` — the old
`artmuseum.daegu.go.kr` host is dead. Do not "fix" URLs back to it.

## URLs

```
List:   GET https://daeguartmuseum.or.kr/index.do?menu_id=00000729   (현재전시)
Detail: GET https://daeguartmuseum.or.kr/index.do
            ?menu_id=00000729&menu_link=/front/ehi/ehiViewFront.do&ehi_id=<EHI_ID>
```

The site's own `fnView()` does a form POST, but plain GET with `ehi_id` in the
query serves the same page.

## Selectors

- Card: `div.c_exh_lst div.item` — the `EHI_########` id regexed from the
  `javascript:fnView('…')` href; title `.item_tit` (scoped to the anchor — an
  audio-guide popup repeats the title below); date `span.info_date`
  ("YYYY-MM-DD~YYYY-MM-DD"); thumb `span.img img`. The per-hall 장소 value is
  visible on the card but intentionally not extracted (normalize has no
  per-hall field).
- Detail prose: `div.exh_view_intro div.intro` (HWP-editor content), fallback
  meta description.

## Quirks

- Notice rows like "2026 전시일정" carry legitimate-looking dates — skipped by
  a title guard plus the requirement of a parseable range.
- 8 items/page by default; further pages are POST-driven, but all current
  shows fit on page 1 at recon time.
- Media gate: `media_category(title, detail prose)`. The recon-day lineup is
  painting-heavy → zero yields, which is correct.
