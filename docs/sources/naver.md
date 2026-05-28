# Naver 전시 검색 — extraction notes

## Status: BLOCKED

**Recon performed:** 2026-05-28

Naver's search results do NOT contain structured exhibition card data (title / venue_name / date_range)
in server-rendered static HTML. Both desktop and mobile endpoints were tested; neither returns parseable
exhibition cards for a static httpx-based extractor.

---

## URLs tested

| URL | UA | Result |
|---|---|---|
| `https://search.naver.com/search.naver?where=nexearch&query=사진+전시` | Desktop Chrome | **BLOCKED — 403 security wall** ("검색 서비스 이용이 제한되었습니다") |
| `https://m.search.naver.com/search.naver?where=m&query=사진+전시` | Mobile Safari | 200 OK, 564 KB — but only blog posts / AI briefing |
| `https://m.search.naver.com/search.naver?where=m_expview&query=사진전시` | Mobile Safari | Same as above — no exhibition cards |
| `https://m.search.naver.com/search.naver?where=m&query=사진전&type=exhbt` | Mobile Safari | Same — blog posts only |
| `https://m.search.naver.com/search.naver?where=m&query=서울+전시회` | Mobile Safari | Blog/influencer posts, no structured cards |
| `https://m.map.naver.com/search.nhn?query=사진전시` | Mobile Safari | Pure SPA (Vite/React), client-rendered only |
| `https://m.booking.naver.com/booking/13/bizes?key=exhibition` | Mobile Safari | Redirects to error page (unsupported URL) |
| `https://openapi.naver.com/v1/search/exhibition.json?query=…` | — | **401 Unauthorized** (requires API key) |

---

## What the mobile page actually contains

Naver mobile search (564 KB HTML) for "사진 전시" has six server-rendered blocks via the
`fender_renderer` SSR system:

| Block ID | Content |
|---|---|
| `ai-briefing/prs_template_aib_answer_mo.ts` | AI-generated summary paragraph (unstructured text) |
| `review/prs_template_v2_review_ugc_single_intention_mo.ts` | 7 blog/cafe posts about exhibitions |
| `clip/prs_template_v2_clip_overlaytext_mo.ts` | Short videos |
| `qra/prs_template_qra_mo.ts` | Q&A (empty) |
| `web/prs_template_v2_web_basic_mo.ts` | General web links (museum sites) |
| `image/prs_template_v2_image_basic_mo.ts` | Image results |

The `review` block contains 7 `ugcItem` elements — each is a blog/cafe post. They mention
exhibitions in their text bodies but have **no structured fields** (no venue_name, no date_range
separate from the post publication date).

The "green exhibition cards" visible in a browser (with venue, dates, image) are loaded via
client-side JavaScript after the initial page render and do not appear in the static HTML.

---

## Why this is BLOCKED (not just a UA issue)

1. **Desktop search**: 403 security wall regardless of UA. Naver rate-limits IPs that issue
   automated requests even with a correct browser UA.

2. **Mobile search**: Returns 200 with HTML, but the structured exhibition data (title/venue/date)
   is injected via JavaScript by the fender renderer's client-side hydration.
   The static HTML only contains UGC blog posts and AI text.

3. **Naver Open API**: `openapi.naver.com/v1/search/exhibition.json` exists and returns 401,
   confirming the endpoint exists but requires OAuth credentials (client_id / client_secret).
   Using the API would require registering an app at https://developers.naver.com/.

---

## Possible paths to unblock

| Option | Effort | Notes |
|---|---|---|
| **Naver Open API** | Low-Medium | Register app at developers.naver.com, get client_id/secret. The `/v1/search/exhibition` endpoint may return structured JSON. Free tier: 25,000 calls/day. |
| **Playwright** | Medium | Would allow full browser rendering to extract the client-side exhibition cards. Separate plan required. |
| **Naver Blog API** | Low | The Open API has a `/v1/search/blog` endpoint. Could search for 사진전시 posts, but results are unstructured blog text — same problem as the static HTML. |

**Recommended path:** Register for Naver Open API and test the `/v1/search/exhibition` endpoint.
If it returns structured exhibition data, this is a low-effort unblock (add API key to env,
change HTTP method to GET with auth header). No Playwright needed.

---

## Robots & manners

- Desktop access: blocked
- Mobile crawling: technically 200 but the content is UGC, and structured data is client-rendered
- Naver's robots.txt: `https://www.naver.com/robots.txt` — generally prohibits automated crawling
  of search results
- Naver Open API ToS: allows up to 25,000 calls/day, requires attribution

---

## Pagination

Not applicable (blocked). If unblocked via Open API:
- `start` parameter for offset (1, 11, 21, …)
- `display` for page size (max 100 per call)
