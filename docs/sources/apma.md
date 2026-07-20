# 아모레퍼시픽미술관 (APMA, apma.amorepacific.com) — extraction notes

Verified 2026-07-20.

## Venue

- 아모레퍼시픽미술관 / Amorepacific Museum of Art — 서울특별시 용산구 한강대로 100 (Amorepacific HQ, Yongsan).
- Corporate collection museum, all media. **Not** photo-only → every card passes through the shared `_media.media_category` gate.

## URLs

- **List (current)**: GET `https://apma.amorepacific.com/contents/exhibition/index.do` — first page is server-rendered. **First page only**: the AJAX archive `/contents/exhibition/ajax/index.do` holds past shows and is out of scope.
- **Detail**: `https://apma.amorepacific.com/contents/exhibition/{id}/view.do` (numeric id).

## List page structure

```html
<ul id="photoLst_wrap">
  <li class="photoLst">
    <a href="/contents/exhibition/4055621/view.do">
      <div class="thumbBox"><div class="thumb"><em>
        <img class="lazy" data-src="https://image-apma.amorepacific.com/upload/exhibition/m/....jpg">
      </em></div></div>
      <span class="tit"><em><b><strong>[APMA, CHAPTER FIVE: …] 육명심, 예술가의 초상 </strong></b></em></span>
    </a>
  </li>
  <li class="photoLst"><div class="fixedBox">…</div></li>  <!-- decorative, NO <a> — skip -->
  …
</ul>
```

- Only `li.photoLst` **with** an anchor matching `^/contents/exhibition/\d+/view\.do$` are cards; decorative `fixedBox` badge/logo items are interleaved and must be skipped.
- Thumbnail is lazy-loaded: real URL in `img.lazy[data-src]`, already absolute (`image-apma.amorepacific.com`).
- Title: `span.tit` combined text (nested `em > b > strong`).
- **No dates on the list** — dates come from each detail page.
- 2026-07-20 snapshot: 10 cards — the 《APMA, CHAPTER FIVE》 headline (육명심), seven per-section `작품소개` sub-pages, one `전시관람 예약` reservation card, one Mark Bradford sub-page.

## Detail page extraction

| Field | Source |
|---|---|
| title | `h3.tit`; fallback: list-card title |
| date_range | `li.place` text (`2026.04.01(수) – 2026.08.02(일) \| 미술관 1F로비, …`) → part before `\|` → `_detail.extract_date_range` (Korean weekday parens + en-dash already handled) |
| description | **not server-rendered** — lives in an inline `let content = {...};` JS blob; `"description1"` is a JSON string literal of prose HTML. Regex the literal (`"description1"\s*:\s*"((?:[^"\\]|\\.)*)"`), `json.loads` re-wrapped in quotes to undo `\"`/`\/`/`\uXXXX` escapes, parse as HTML, `paragraphs_text`. Fallback `meta_description` |
| organizer | `p.s_txt` (`기획: 아모레퍼시픽미술관 (APMA)`) — noted, not emitted |
| poster_image_url | list-card `data-src` (detail pages have no distinct og:image poster) |
| artists | `[]` |

## Sub-page / dedupe policy

The list mixes the headline show with per-artwork `작품소개` sub-pages sharing one date range. There is **no standalone parent card** in the current snapshot, and sub-pages like 육명심, 예술가의 초상 or 한국 현대사진, 멈춤과 흐름 are effectively per-section shows worth listing — so **no dedupe**: every card that passes the media gate is yielded.

## Media filter (verified against live fixtures)

- `[APMA, CHAPTER FIVE] 작품소개: 한국 현대사진, 멈춤과 흐름` → passes via broad `사진` in the **title**.
- `[APMA, CHAPTER FIVE: …] 육명심, 예술가의 초상` → title has no keyword; passes via strict compounds (`사진가`, `사진작가`) in the blob **prose** → `사진`.
- `작품소개: 백남준과 TV 너머의 세계` → title has no keyword (`TV` is not in the broad set); passes via strict video compounds (`비디오 아트`, `미디어 아트`) in the prose → `영상`.
- `작품소개: 회화 속 세계들` (painting) → no match anywhere → dropped.
- `전시관람 예약`, sculpture/painting sub-pages, Mark Bradford piece → dropped.
- 2026-07-20 live result: **10 cards pre-filter → 3 yielded** (사진 ×2, 영상 ×1).

## Anti-bot

The site sits behind **Imperva Incapsula**. Plain `curl`/httpx with the desktop-Chrome UA (`Mozilla/5.0 (Macintosh; …) Chrome/120.0 Safari/537.36`) passes cleanly (verified 2026-07-20). If blocked, retry with that exact UA.

## Failure handling

- tenacity retry on `httpx.TransportError` (exp backoff 1→16 s, 3 attempts, reraise).
- A failed detail page falls back to the **title-only** media gate (card kept with `date_range=None` if the title alone passes); the crawl continues.

## Robots & manners

- 1 s delay between detail fetches; `follow_redirects=True`; timeout 30 s.
- First list page only (~10 detail fetches per run).
