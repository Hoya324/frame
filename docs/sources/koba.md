# KOBA — 한국국제방송영상기자재전 (Korea International Broadcast, Audio & Lighting Exhibition)

## Overview

KOBA is an annual single-event trade show focused on broadcast/audio/lighting equipment, held at COEX, Seoul. Unlike recurring exhibition-list sources, the extractor yields one `RawExhibition` row per crawl — the current edition as listed on the official info page.

## Site Architecture

- **Main SPA**: `https://www.kobashow.com/` — React SPA (`<div id="root">`), all subpages return the same 1858-byte shell. **Useless for scraping.**
- **Conference subsite**: `https://conference.kobashow.com/` — Classic ASP/server-rendered. Contains:
  - `kor/about/info.asp` — Exhibition overview with structured table (기간, 장소, 규모) **← primary source**
  - `kor/seminar/conference.asp` — Media Conference sub-event
  - `kor/seminar/world.asp` — World Media Forum sub-event

## Data Source

**URL:** `https://conference.kobashow.com/kor/about/info.asp`

The page is fully server-rendered (no JS required). It contains:
- `h4` tag: full edition title, e.g. `KOBA 2025 (제 33회 국제 방송·미디어·음향·조명 전시회)`
- `table > tr` rows: `기간` (date range), `장소` (venue), `개장시간` (hours), `규모` (area)
- `p` paragraph: organizer names embedded in text, e.g. `한국이앤엑스와 한국방송기술인연합회가 공동주최하는`
- `img[alt]` for sponsor logos (secondary organizer extraction)

## Parsing Strategy

```
h4  → title
table tr: th[text()='기간'] next td → date_range
table tr: th[text()='장소'] next td → venue_name (strip address in parentheses)
p (first paragraph containing '주최') → extract organizer via regex
```

The organizer is extracted from the first paragraph by finding text before `와` or `이` (Korean connector):
- Pattern: `^([^와이]+(?:이앤엑스|연합회|협회|진흥원))`

## Output Shape

```python
RawExhibition(
    source=SourceName.KOBA,
    source_url="https://conference.kobashow.com/kor/about/info.asp",
    raw={
        "title": "KOBA 2025 (제 33회 국제 방송·미디어·음향·조명 전시회)",
        "venue_name": "COEX 전시장 A, C, D홀 및 컨퍼런스센터",
        "date_range": "2025년 5월 20일(화) ~ 23일(금)",
        "organizer": "한국이앤엑스",
        "exhibition_type_text": "박람회",
    }
)
```

## Organizer vs Venue

KOBA is hosted **at** COEX but **organized by** 한국이앤엑스 + 한국방송기술인연합회. This exercises the Organizer ≠ Venue path in the entity resolver.

## Pagination

None — single page fetch, single result per crawl.

## Robots / Manners

No `robots.txt` restrictions on the conference subsite. Single GET request per crawl cycle. No auth required.

## Annual Cycle

- KOBA 2025: May 20–23, 2025 (33rd edition)
- KOBA 2026: ~May 2026 (info page updates ~3-4 months before the event)
- The info page always reflects the current/upcoming edition — crawler naturally picks up the new year once the page is updated.

## Known Quirks

- `kobashow.com` home and all SPA routes are completely useless for static scraping.
- The info page occasionally shows the previous year's data if updated late (e.g., still showing 2025 data in early 2026).
- Venue string includes a parenthetical address: `COEX 전시장 A, C, D홀 및 컨퍼런스센터 (서울특별시 강남구 영동대로 513 코엑스)` — the extractor strips the parenthetical.
- Organizer list is rendered as logo images; primary organizer is extracted from paragraph text.
