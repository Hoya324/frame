# 백남준아트센터 (Nam June Paik Art Center, njp.ggcf.kr) — extraction notes

Verified 2026-07-20.

## Scope

Single-purpose venue — the Nam June Paik centre shows video/media art
exclusively, so every card is seeded `category = "영상"` unconditionally (no
`_media` keyword gate). Only **current/upcoming** shows are crawled: the
`/exhibitions` page lists them directly; the yearly archive under
`/exhibitions/more?year=` is deliberately not crawled.

## URLs

- **List page**: GET `https://njp.ggcf.kr/exhibitions` — single
  server-rendered page, **no pagination**.
- **Detail page**: `https://njp.ggcf.kr/exhibitions/{id}` (the card's `a.title`
  href, relative).

## Card HTML structure

```html
<li>
  <a href="/exhibitions/244">
    <div class="thumb"
         style="background-image: url('/storage/upload/2026/06/19/….jpg');">
    </div>
  </a>
  <div class="meta-info">
    <a href="…?tag=전시" class="category">전시</a>
    <a href="/exhibitions/244" class="title">별, 괘卦</a>
    <div class="date">2026. 7. 16.—2027. 2. 14.</div>
  </div>
</li>
```

Key extraction points:

- `a.title[href="/exhibitions/{id}"]` → title + detail URL (absolutize with
  `https://njp.ggcf.kr`). Iterate `a.title` and climb to the wrapping `<li>`.
- `div.date` → `"2026. 7. 16.—2027. 2. 14."` (dotted parts, **em-dash**
  separator). `_detail.extract_date_range` handles both and emits canonical
  `YYYY.MM.DD~YYYY.MM.DD`.
- `div.thumb` inline style → `background-image: url('/storage/upload/…')`;
  extract with a regex, absolutize.
- A second (commented-out) `a.category` sits in the HTML — selectolax ignores
  comments, no special handling needed.

Venue constants: `백남준아트센터` / `경기` / `경기도 용인시 기흥구 백남준로 10`.

## Detail page (shared ggcf.kr CMS — same platform as gmoma.ggcf.kr)

- Description prose in `div.content` (`paragraphs_text`), meta-description
  fallback.
- `<dl>` metadata block: `<dt>장소</dt>`, `<dt>일시</dt>`, `<dt>기획</dt>`,
  `<dt>참여작가</dt>` (→ artists), `<dt>주최주관</dt>`. Artists are
  comma-separated; group entries may carry a parenthesised member roster
  ("알오에스(강류, 김시월, …)"), so the split is paren-aware.
- `og:image` exists in the markup but is **empty** today; when the CMS starts
  populating it, the extractor prefers it over the list thumbnail as poster.
- No admission/fee row in the `<dl>` → `fee_text` omitted.

Detail fetch failures never abort the crawl (list-level fields are kept).

## Exhibition count (2026-07-20 snapshot)

4 cards: 별, 괘卦 (244) / 달들 (243) / 2026 백남준의 도시 (241) /
NJP 라운지 2. 장윤영 (245).

## Robots & manners

- No robots.txt restriction found; public art centre run by 경기문화재단.
- 1-second delay between detail fetches; Chrome desktop User-Agent.
