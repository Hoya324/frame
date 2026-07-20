# 경기도미술관 (Gyeonggi Museum of Modern Art, gmoma.ggcf.kr) — extraction notes

Verified 2026-07-20.

## Scope

General contemporary-art museum in Ansan — most shows are painting /
participatory, so every card passes the shared photo/film/media keyword gate
(`crawler/sources/_media.py`): broad keywords over the **title**, strict
compounds over the **detail description**. Expect 0-1 yields per live run —
zero yields is the filter working, not a parser fault (the 2026-07-20
snapshot yields 0).

## URLs

- **List pages** (both crawled, deduped by URL):
  - GET `https://gmoma.ggcf.kr/exhibitions?progress=now` — current shows
  - GET `https://gmoma.ggcf.kr/exhibitions?progress=yet` — upcoming shows
  - Single server-rendered pages on the shared ggcf.kr CMS (same platform as
    njp.ggcf.kr), **no pagination**.
- **Detail page**: `https://gmoma.ggcf.kr/exhibitions/{id}`.

## List HTML structure

ONE `li.item-list` container per page wraps every card (NOT one `<li>` per
card — a deviation from the original recon):

```html
<li class="item-list">
  <div>
    <a href="/exhibitions/206">
      <div class="img-box"><img src="/storage/upload/…jpg" alt=""></div>
      <p>《우리의 여름에게》</p>
      <p class="date"> 2026. 07. 16. — 2026. 09. 27. </p>
    </a>
  </div>
  <div>…next card…</div>
</li>
```

An empty `?progress=yet` renders the bare `li.item-list` with no anchors
(the 2026-07-20 snapshot has no upcoming shows).

Key extraction points:

- `li.item-list a[href="/exhibitions/{id}"]` → card anchor (absolutize with
  `https://gmoma.ggcf.kr`).
- Title: the `<p>` **without** the `date` class (usually 《…》-wrapped).
- `p.date` → `"2026. 07. 16. — 2026. 09. 27."` (dotted parts, **em-dash**);
  `_detail.extract_date_range` canonicalizes to `YYYY.MM.DD~YYYY.MM.DD`.
  The permanent collection show is **open-ended** (`"2023. 09. 15. — "`) —
  `extract_date_range` returns `None` there and `date_range=None` is fine
  downstream.
- `div.img-box img[src]` → poster (relative `/storage/upload/…` path).

Venue constants: `경기도미술관` / `경기` / `경기도 안산시 단원구 동산로 268`.

## Detail page

- Description prose in `div.view-content` (`paragraphs_text`); prefer it over
  `div.content`, which on some pages also swallows site chrome (footer/terms).
  Meta-description fallback.
- `<dl>` metadata block: `<dt>장소</dt>`, `<dt>참여작가</dt>` (→ artists),
  `<dt>기획</dt>`, `<dt>주최·주관</dt>`, …. Artists are comma-separated;
  group entries may carry a parenthesised member roster
  ("알오에스(강류, 김시월, …)"), so the split is paren-aware.
- No admission/fee row in the `<dl>` → `fee_text` omitted.
- The detail is fetched **before** the media gate so the strict compound tier
  can see the description; a failed fetch degrades to gating on the title
  alone (crawl never aborts).

## Exhibition count (2026-07-20 snapshot)

- `?progress=now`: 3 cards — 《우리의 여름에게》 (206, 26 청년작가 group show),
  《눈-길》 (203, participatory collection program), 상설전 《멈춰서서》 (49,
  open-ended outdoor sculpture). **None** pass the media gate → 0 yields.
- `?progress=yet`: 0 cards.

## Robots & manners

- No robots.txt restriction found; public museum run by 경기문화재단.
- 1-second delay between detail fetches; Chrome desktop User-Agent.
