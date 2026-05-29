# Web App & Discovery — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the public discovery web app (Next.js + Tailwind) that reads the static catalog JSON and lets users browse exhibitions by time, swipe, search/filter, map, and detail — responsive and installable as a PWA. No login yet (added in Plan 3).

**Architecture:** A Next.js App Router app under `web/`, statically exported, reading `web/public/data/exhibitions.json` (produced by the crawler `export-json` from Plan 1). All filtering/sorting is client-side over the in-memory catalog (~100s of items). Pure logic (catalog parsing, filters, status/D-day) is unit-tested with Vitest; UI is assembled from small focused components and verified in the browser. The visual language is strict black/white (BeReal tone) with Linear-grade restraint.

**Tech Stack:** Next.js 15 (App Router) + React 19, TypeScript, Tailwind CSS, MapLibre GL JS + OSM tiles, `next-pwa` (or manual service worker), Vitest + @testing-library/react.

---

## Background for the implementer

- This is a **monorepo**: the existing Python crawler stays at the repo root; the web app lives in a new `web/` subdirectory with its own `package.json`. All commands in this plan run from `web/` unless noted.
- The catalog JSON contract is defined in Plan 1 (`docs/superpowers/plans/2026-05-30-crawler-json-export.md`) and the design in `docs/superpowers/specs/2026-05-30-exhibition-site-design.md`. Re-read §3 (design tone), §4 (IA & screens), §6 (catalog shape) before starting.
- **Design tokens (BW / BeReal tone):** background `#000`/`#0a0a0a`, panel `#0c0c0c`/`#141414`, hairline borders `rgba(255,255,255,.13)`, text `#fff` / `#9a9a9a` / `#5e5e5e`. **No color accent** — the accent is inversion (white bg + black text) for active chips, primary buttons, and D-day badges. Bold tight headlines (font-weight 800, letter-spacing ~ -0.04em). Poster images keep color.
- **Icons are placeholders today.** Use `lucide-react` for all icons — never emoji — and polish hover/active/focus/disabled states (spec §3 "완성도 요구사항").
- For dev data before Plan 1 runs live: a small committed sample `web/public/data/exhibitions.json` is created in Task 2 so the app renders.

## File Structure

```
web/
  package.json, tsconfig.json, next.config.mjs, tailwind.config.ts, postcss.config.mjs
  vitest.config.ts, vitest.setup.ts
  public/
    data/exhibitions.json        # sample committed; overwritten by crawler export-json
    manifest.webmanifest
    icons/icon-192.png, icon-512.png
  src/
    app/
      layout.tsx                 # root: theme, fonts, <Nav/>
      globals.css                # tailwind + design tokens
      page.tsx                   # 둘러보기 (home, time mode) + swipe toggle
      search/page.tsx            # 검색/필터
      map/page.tsx               # 지도
      exhibitions/[id]/page.tsx  # 상세
    components/
      Nav.tsx                    # top nav (desktop) / bottom tab (mobile)
      ExhibitionCard.tsx
      PosterImage.tsx
      StatusBadge.tsx
      FilterChips.tsx
      ScrapButton.tsx            # visual-only placeholder until Plan 3
      SwipeDeck.tsx
      MapView.tsx
    lib/
      catalog.ts                 # load + parse catalog, types
      filters.ts                 # pure filter/sort/search
      status.ts                  # status + D-day helpers
      regions.ts                 # district → region grouping for map
```

Split by responsibility: pure logic in `lib/` (unit-tested), presentation in `components/`, routing in `app/`.

---

## Task 1: Scaffold Next.js + Tailwind + BW theme

**Files:**
- Create: `web/package.json`, `web/tsconfig.json`, `web/next.config.mjs`, `web/tailwind.config.ts`, `web/postcss.config.mjs`, `web/src/app/layout.tsx`, `web/src/app/globals.css`, `web/src/app/page.tsx`, `web/.gitignore`

- [ ] **Step 1: Create the Next.js app non-interactively**

Run (from repo root):
```bash
npx create-next-app@latest web --ts --tailwind --eslint --app --src-dir --import-alias "@/*" --no-turbopack --use-npm
```
Expected: `web/` created with App Router, Tailwind, TS. If it prompts, accept defaults matching the flags.

- [ ] **Step 2: Add design tokens to `web/src/app/globals.css`**

Replace the file body's top (keep the `@tailwind` directives) with:
```css
@tailwind base;
@tailwind components;
@tailwind utilities;

:root {
  --bg: #000;
  --bg2: #0a0a0a;
  --panel: #0c0c0c;
  --panel2: #141414;
  --line: rgba(255, 255, 255, 0.13);
  --line2: rgba(255, 255, 255, 0.22);
  --tx: #fff;
  --tx2: #9a9a9a;
  --tx3: #5e5e5e;
}

html, body {
  background: var(--bg);
  color: var(--tx);
  -webkit-font-smoothing: antialiased;
  letter-spacing: -0.01em;
}
```

- [ ] **Step 3: Map tokens into Tailwind in `web/tailwind.config.ts`**

Set the `theme.extend.colors` so utilities like `bg-panel`, `border-line`, `text-tx2` work:
```ts
import type { Config } from "tailwindcss";

const config: Config = {
  content: ["./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        bg: "var(--bg)",
        bg2: "var(--bg2)",
        panel: "var(--panel)",
        panel2: "var(--panel2)",
        line: "var(--line)",
        line2: "var(--line2)",
        tx: "var(--tx)",
        tx2: "var(--tx2)",
        tx3: "var(--tx3)",
      },
      borderColor: { DEFAULT: "var(--line)" },
    },
  },
  plugins: [],
};
export default config;
```

- [ ] **Step 4: Replace `web/src/app/page.tsx` with a placeholder**

```tsx
export default function Home() {
  return (
    <main className="mx-auto max-w-[1180px] px-7 py-10">
      <h1 className="text-4xl font-extrabold tracking-tight">FRAME</h1>
      <p className="mt-3 text-tx2">전시 디스커버리 — 준비 중</p>
    </main>
  );
}
```

- [ ] **Step 5: Run the dev server and verify**

Run (from `web/`): `npm run dev`
Open http://localhost:3000 — expect a black page with white "FRAME" heading. Stop the server (Ctrl-C).

- [ ] **Step 6: Commit**

```bash
git add web
git commit -m "feat(web): scaffold Next.js + Tailwind with BW design tokens"
```

---

## Task 2: Catalog types, loader, and sample data

**Files:**
- Create: `web/src/lib/catalog.ts`, `web/public/data/exhibitions.json`, `web/vitest.config.ts`, `web/vitest.setup.ts`
- Test: `web/src/lib/catalog.test.ts`
- Modify: `web/package.json` (test scripts + deps)

- [ ] **Step 1: Add Vitest tooling**

Run (from `web/`):
```bash
npm i -D vitest @testing-library/react @testing-library/jest-dom jsdom @vitejs/plugin-react
```
Create `web/vitest.config.ts`:
```ts
import react from "@vitejs/plugin-react";
import { defineConfig } from "vitest/config";
import path from "node:path";

export default defineConfig({
  plugins: [react()],
  resolve: { alias: { "@": path.resolve(__dirname, "src") } },
  test: { environment: "jsdom", setupFiles: ["./vitest.setup.ts"], globals: true },
});
```
Create `web/vitest.setup.ts`:
```ts
import "@testing-library/jest-dom/vitest";
```
Add to `web/package.json` `"scripts"`: `"test": "vitest run"`, `"test:watch": "vitest"`.

- [ ] **Step 2: Write the failing test**

```ts
// web/src/lib/catalog.test.ts
import { describe, expect, it } from "vitest";
import { parseCatalog, type Catalog } from "@/lib/catalog";

const RAW = {
  generated_at: "2026-05-30T06:54:00+00:00",
  exhibitions: [
    {
      id: "e1", title: "빛과 시간의 기록", title_en: null,
      poster_image_url: "https://x/p.jpg", description: "d",
      medium: "photo", exhibition_type: "solo", genre_tags: ["doc"],
      fee_type: "free", price_min: null, price_max: null,
      start_date: "2026-05-30", end_date: "2026-07-20",
      status: "ongoing", open_hours: "10-18",
      venue: { id: "v1", name: "한미", region: "서울", district: "삼청", lat: 37.5, lng: 126.9 },
      artists: [{ id: "a1", name: "김작가" }],
      source_url: "https://s/1", featured: true, popularity_score: null,
    },
  ],
  venues: [{ id: "v1", name: "한미", name_en: null, venue_type: "museum",
    region: "서울", district: "삼청", address: "a", country: "KR",
    lat: 37.5, lng: 126.9, website: null }],
  artists: [{ id: "a1", name: "김작가", name_en: null }],
};

describe("parseCatalog", () => {
  it("parses into typed catalog", () => {
    const cat: Catalog = parseCatalog(RAW);
    expect(cat.exhibitions).toHaveLength(1);
    expect(cat.exhibitions[0].venue?.district).toBe("삼청");
    expect(cat.exhibitions[0].featured).toBe(true);
    expect(cat.generatedAt).toBe("2026-05-30T06:54:00+00:00");
  });
});
```

- [ ] **Step 3: Run test to verify it fails**

Run: `npm run test -- catalog`
Expected: FAIL — cannot find module `@/lib/catalog`.

- [ ] **Step 4: Write the implementation**

```ts
// web/src/lib/catalog.ts
export type Status = "upcoming" | "ongoing" | "past" | "unknown";

export interface VenueEmbed {
  id: string; name: string; region: string | null; district: string | null;
  lat: number | null; lng: number | null;
}
export interface Exhibition {
  id: string; title: string; titleEn: string | null;
  posterImageUrl: string | null; description: string | null;
  medium: string | null; exhibitionType: string | null; genreTags: string[];
  feeType: string | null; priceMin: number | null; priceMax: number | null;
  startDate: string | null; endDate: string | null;
  status: Status; openHours: string | null;
  venue: VenueEmbed | null; artists: { id: string; name: string }[];
  sourceUrl: string | null; featured: boolean; popularityScore: number | null;
}
export interface Venue {
  id: string; name: string; nameEn: string | null; venueType: string | null;
  region: string | null; district: string | null; address: string | null;
  country: string | null; lat: number | null; lng: number | null; website: string | null;
}
export interface Catalog {
  generatedAt: string;
  exhibitions: Exhibition[];
  venues: Venue[];
  artists: { id: string; name: string; nameEn: string | null }[];
}

/* eslint-disable @typescript-eslint/no-explicit-any */
export function parseCatalog(raw: any): Catalog {
  return {
    generatedAt: raw.generated_at,
    exhibitions: (raw.exhibitions ?? []).map(
      (e: any): Exhibition => ({
        id: e.id, title: e.title, titleEn: e.title_en ?? null,
        posterImageUrl: e.poster_image_url ?? null, description: e.description ?? null,
        medium: e.medium ?? null, exhibitionType: e.exhibition_type ?? null,
        genreTags: e.genre_tags ?? [], feeType: e.fee_type ?? null,
        priceMin: e.price_min ?? null, priceMax: e.price_max ?? null,
        startDate: e.start_date ?? null, endDate: e.end_date ?? null,
        status: (e.status ?? "unknown") as Status, openHours: e.open_hours ?? null,
        venue: e.venue
          ? { id: e.venue.id, name: e.venue.name, region: e.venue.region ?? null,
              district: e.venue.district ?? null, lat: e.venue.lat ?? null, lng: e.venue.lng ?? null }
          : null,
        artists: e.artists ?? [],
        sourceUrl: e.source_url ?? null, featured: !!e.featured,
        popularityScore: e.popularity_score ?? null,
      }),
    ),
    venues: (raw.venues ?? []).map((v: any): Venue => ({
      id: v.id, name: v.name, nameEn: v.name_en ?? null, venueType: v.venue_type ?? null,
      region: v.region ?? null, district: v.district ?? null, address: v.address ?? null,
      country: v.country ?? null, lat: v.lat ?? null, lng: v.lng ?? null, website: v.website ?? null,
    })),
    artists: (raw.artists ?? []).map((a: any) => ({ id: a.id, name: a.name, nameEn: a.name_en ?? null })),
  };
}

export async function loadCatalog(): Promise<Catalog> {
  const data = (await import("../../public/data/exhibitions.json")).default;
  return parseCatalog(data);
}
```

- [ ] **Step 5: Create a committed sample `web/public/data/exhibitions.json`**

Write a small but realistic sample (≥6 exhibitions across statuses `ongoing`/`upcoming`, with venues that have lat/lng in Seoul, varied `end_date` so D-day logic is visible). Use the same shape as `RAW` in the test. This file is overwritten by the crawler `export-json` in production but lets the app render in dev/CI.

- [ ] **Step 6: Run test to verify it passes**

Run: `npm run test -- catalog`
Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add web
git commit -m "feat(web): catalog types, parser, loader + sample data"
```

---

## Task 3: Status & D-day helpers

**Files:**
- Create: `web/src/lib/status.ts`
- Test: `web/src/lib/status.test.ts`

- [ ] **Step 1: Write the failing test**

```ts
// web/src/lib/status.test.ts
import { describe, expect, it } from "vitest";
import { daysUntil, ddayLabel, isClosingSoon } from "@/lib/status";

const TODAY = new Date("2026-05-30T00:00:00+09:00");

describe("status helpers", () => {
  it("daysUntil counts whole days to end date", () => {
    expect(daysUntil("2026-06-02", TODAY)).toBe(3);
    expect(daysUntil("2026-05-30", TODAY)).toBe(0);
    expect(daysUntil(null, TODAY)).toBeNull();
  });
  it("ddayLabel formats", () => {
    expect(ddayLabel("2026-06-02", TODAY)).toBe("D-3");
    expect(ddayLabel("2026-05-30", TODAY)).toBe("D-day");
    expect(ddayLabel(null, TODAY)).toBeNull();
  });
  it("isClosingSoon within 7 days inclusive", () => {
    expect(isClosingSoon("2026-06-06", TODAY)).toBe(true);
    expect(isClosingSoon("2026-06-30", TODAY)).toBe(false);
    expect(isClosingSoon(null, TODAY)).toBe(false);
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `npm run test -- status`
Expected: FAIL — cannot find `@/lib/status`.

- [ ] **Step 3: Write the implementation**

```ts
// web/src/lib/status.ts
const MS_PER_DAY = 86_400_000;

function atMidnight(d: Date): number {
  return Math.floor(new Date(d.getFullYear(), d.getMonth(), d.getDate()).getTime() / MS_PER_DAY);
}

export function daysUntil(endDate: string | null, today: Date = new Date()): number | null {
  if (!endDate) return null;
  const end = new Date(endDate + "T00:00:00");
  return atMidnight(end) - atMidnight(today);
}

export function ddayLabel(endDate: string | null, today: Date = new Date()): string | null {
  const d = daysUntil(endDate, today);
  if (d === null) return null;
  return d <= 0 ? "D-day" : `D-${d}`;
}

export function isClosingSoon(endDate: string | null, today: Date = new Date()): boolean {
  const d = daysUntil(endDate, today);
  return d !== null && d >= 0 && d <= 7;
}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `npm run test -- status`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add web/src/lib/status.ts web/src/lib/status.test.ts
git commit -m "feat(web): status + D-day helpers"
```

---

## Task 4: Filter / sort / search

**Files:**
- Create: `web/src/lib/filters.ts`
- Test: `web/src/lib/filters.test.ts`

- [ ] **Step 1: Write the failing test**

```ts
// web/src/lib/filters.test.ts
import { describe, expect, it } from "vitest";
import { applyFilters, searchExhibitions, type FilterState } from "@/lib/filters";
import type { Exhibition } from "@/lib/catalog";

function ex(p: Partial<Exhibition>): Exhibition {
  return {
    id: "x", title: "T", titleEn: null, posterImageUrl: null, description: null,
    medium: "photo", exhibitionType: "solo", genreTags: [], feeType: "free",
    priceMin: null, priceMax: null, startDate: "2026-05-01", endDate: "2026-06-30",
    status: "ongoing", openHours: null, venue: null, artists: [],
    sourceUrl: null, featured: false, popularityScore: null, ...p,
  };
}
const EMPTY: FilterState = { statuses: [], mediums: [], types: [], freeOnly: false, regions: [] };

describe("applyFilters", () => {
  it("filters by status", () => {
    const out = applyFilters([ex({ id: "a", status: "ongoing" }), ex({ id: "b", status: "upcoming" })],
      { ...EMPTY, statuses: ["ongoing"] });
    expect(out.map((e) => e.id)).toEqual(["a"]);
  });
  it("filters freeOnly", () => {
    const out = applyFilters([ex({ id: "a", feeType: "free" }), ex({ id: "b", feeType: "paid" })],
      { ...EMPTY, freeOnly: true });
    expect(out.map((e) => e.id)).toEqual(["a"]);
  });
  it("empty filters returns all", () => {
    expect(applyFilters([ex({ id: "a" }), ex({ id: "b" })], EMPTY)).toHaveLength(2);
  });
  it("filters by region from venue", () => {
    const out = applyFilters(
      [ex({ id: "a", venue: { id: "v", name: "n", region: "서울", district: "삼청", lat: null, lng: null } }),
       ex({ id: "b", venue: { id: "v2", name: "n", region: "부산", district: null, lat: null, lng: null } })],
      { ...EMPTY, regions: ["서울"] });
    expect(out.map((e) => e.id)).toEqual(["a"]);
  });
});

describe("searchExhibitions", () => {
  it("matches title, artist, venue (case-insensitive)", () => {
    const list = [
      ex({ id: "a", title: "도시의 표면" }),
      ex({ id: "b", artists: [{ id: "1", name: "Kim Test" }] }),
      ex({ id: "c", venue: { id: "v", name: "류가헌", region: null, district: null, lat: null, lng: null } }),
    ];
    expect(searchExhibitions(list, "도시").map((e) => e.id)).toEqual(["a"]);
    expect(searchExhibitions(list, "kim").map((e) => e.id)).toEqual(["b"]);
    expect(searchExhibitions(list, "류가헌").map((e) => e.id)).toEqual(["c"]);
    expect(searchExhibitions(list, "").map((e) => e.id)).toEqual(["a", "b", "c"]);
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `npm run test -- filters`
Expected: FAIL — cannot find `@/lib/filters`.

- [ ] **Step 3: Write the implementation**

```ts
// web/src/lib/filters.ts
import type { Exhibition, Status } from "@/lib/catalog";

export interface FilterState {
  statuses: Status[];
  mediums: string[];
  types: string[];
  freeOnly: boolean;
  regions: string[];
}

export function applyFilters(list: Exhibition[], f: FilterState): Exhibition[] {
  return list.filter((e) => {
    if (f.statuses.length && !f.statuses.includes(e.status)) return false;
    if (f.mediums.length && (!e.medium || !f.mediums.includes(e.medium))) return false;
    if (f.types.length && (!e.exhibitionType || !f.types.includes(e.exhibitionType))) return false;
    if (f.freeOnly && e.feeType !== "free") return false;
    if (f.regions.length) {
      const region = e.venue?.region ?? null;
      if (!region || !f.regions.includes(region)) return false;
    }
    return true;
  });
}

export function searchExhibitions(list: Exhibition[], q: string): Exhibition[] {
  const query = q.trim().toLowerCase();
  if (!query) return list;
  return list.filter((e) => {
    const hay = [
      e.title, e.titleEn ?? "", e.venue?.name ?? "",
      ...e.artists.map((a) => a.name), ...e.genreTags,
    ].join(" ").toLowerCase();
    return hay.includes(query);
  });
}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `npm run test -- filters`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add web/src/lib/filters.ts web/src/lib/filters.test.ts
git commit -m "feat(web): filter/sort/search logic"
```

---

## Task 5: Core presentational components

**Files:**
- Create: `web/src/components/PosterImage.tsx`, `web/src/components/StatusBadge.tsx`, `web/src/components/ScrapButton.tsx`, `web/src/components/ExhibitionCard.tsx`
- Test: `web/src/components/ExhibitionCard.test.tsx`
- Deps: `npm i lucide-react`

- [ ] **Step 1: Write the failing test**

```tsx
// web/src/components/ExhibitionCard.test.tsx
import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { ExhibitionCard } from "@/components/ExhibitionCard";
import type { Exhibition } from "@/lib/catalog";

const E: Exhibition = {
  id: "e1", title: "을지로의 밤", titleEn: null, posterImageUrl: "https://x/p.jpg",
  description: null, medium: "photo", exhibitionType: "group", genreTags: [],
  feeType: "free", priceMin: null, priceMax: null, startDate: "2026-05-01",
  endDate: "2026-06-02", status: "ongoing", openHours: null,
  venue: { id: "v", name: "갤러리 룩스", region: "서울", district: "을지로", lat: null, lng: null },
  artists: [], sourceUrl: null, featured: false, popularityScore: null,
};

describe("ExhibitionCard", () => {
  it("renders title, venue and D-day", () => {
    render(<ExhibitionCard exhibition={E} today={new Date("2026-05-30T00:00:00+09:00")} />);
    expect(screen.getByText("을지로의 밤")).toBeInTheDocument();
    expect(screen.getByText(/갤러리 룩스/)).toBeInTheDocument();
    expect(screen.getByText("D-3")).toBeInTheDocument();
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `npm run test -- ExhibitionCard`
Expected: FAIL — cannot find `@/components/ExhibitionCard`.

- [ ] **Step 3: Write the components**

```tsx
// web/src/components/PosterImage.tsx
import Image from "next/image";

export function PosterImage({ src, alt }: { src: string | null; alt: string }) {
  if (!src) {
    return <div className="h-full w-full bg-panel2" aria-label={`${alt} (포스터 없음)`} />;
  }
  return (
    <Image src={src} alt={alt} fill sizes="(max-width:760px) 50vw, 280px"
      className="object-cover" unoptimized />
  );
}
```

```tsx
// web/src/components/StatusBadge.tsx
import { ddayLabel } from "@/lib/status";
import type { Exhibition } from "@/lib/catalog";

export function StatusBadge({ e, today }: { e: Exhibition; today?: Date }) {
  if (e.status === "upcoming") {
    return <span className="rounded-full bg-bg/80 px-2 py-1 text-[11px] font-medium text-tx">예정</span>;
  }
  const label = ddayLabel(e.endDate, today);
  if (e.status === "ongoing" && label) {
    return <span className="rounded-full bg-white px-2 py-1 text-[11px] font-bold text-black">{label}</span>;
  }
  return <span className="rounded-full border border-line2 bg-bg/60 px-2 py-1 text-[11px] font-bold text-tx">진행중</span>;
}
```

```tsx
// web/src/components/ScrapButton.tsx
"use client";
import { Heart } from "lucide-react";

// Visual-only until Plan 3 wires Supabase persistence.
export function ScrapButton({ active = false }: { active?: boolean }) {
  return (
    <button
      type="button"
      aria-label="스크랩"
      className="flex h-8 w-8 items-center justify-center rounded-full border border-line2 bg-black/45 text-white transition hover:bg-black/70"
    >
      <Heart size={15} fill={active ? "currentColor" : "none"} />
    </button>
  );
}
```

```tsx
// web/src/components/ExhibitionCard.tsx
import Link from "next/link";
import { PosterImage } from "@/components/PosterImage";
import { StatusBadge } from "@/components/StatusBadge";
import { ScrapButton } from "@/components/ScrapButton";
import type { Exhibition } from "@/lib/catalog";

export function ExhibitionCard({ exhibition: e, today }: { exhibition: Exhibition; today?: Date }) {
  return (
    <Link href={`/exhibitions/${e.id}`} className="group block">
      <div className="relative aspect-[3/4] overflow-hidden rounded-[3px] border border-line">
        <PosterImage src={e.posterImageUrl} alt={e.title} />
        <div className="absolute right-2.5 top-2.5"><ScrapButton /></div>
        <div className="absolute bottom-2.5 left-2.5"><StatusBadge e={e} today={today} /></div>
      </div>
      <div className="pt-2.5">
        <div className="text-[14.5px] font-semibold leading-tight">{e.title}</div>
        <div className="mt-1 text-[12.5px] text-tx2">
          {e.venue ? `${e.venue.name}${e.venue.district ? ` · ${e.venue.district}` : ""}` : "장소 미정"}
        </div>
        <div className="mt-1.5 text-[11.5px] text-tx3">
          {[e.medium, e.exhibitionType].filter(Boolean).join(" · ")}
        </div>
      </div>
    </Link>
  );
}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `npm run test -- ExhibitionCard`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add web/src/components web/package.json web/package-lock.json
git commit -m "feat(web): poster, status badge, scrap button, exhibition card"
```

---

## Task 6: Responsive Nav (top nav / bottom tab)

**Files:**
- Create: `web/src/components/Nav.tsx`
- Modify: `web/src/app/layout.tsx`
- Test: `web/src/components/Nav.test.tsx`

- [ ] **Step 1: Write the failing test**

```tsx
// web/src/components/Nav.test.tsx
import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { Nav } from "@/components/Nav";

describe("Nav", () => {
  it("renders the primary destinations", () => {
    render(<Nav />);
    for (const label of ["둘러보기", "검색", "지도", "스크랩"]) {
      expect(screen.getAllByText(label).length).toBeGreaterThan(0);
    }
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `npm run test -- Nav`
Expected: FAIL — cannot find `@/components/Nav`.

- [ ] **Step 3: Write the component**

```tsx
// web/src/components/Nav.tsx
import Link from "next/link";
import { Compass, Search, Map, Heart, User } from "lucide-react";

const ITEMS = [
  { href: "/", label: "둘러보기", icon: Compass },
  { href: "/search", label: "검색", icon: Search },
  { href: "/map", label: "지도", icon: Map },
  { href: "/scrap", label: "스크랩", icon: Heart },
  { href: "/me", label: "마이", icon: User },
];

export function Nav() {
  return (
    <>
      {/* desktop top nav */}
      <header className="sticky top-0 z-20 hidden border-b border-line bg-black md:block">
        <div className="mx-auto flex h-14 max-w-[1180px] items-center gap-7 px-7">
          <Link href="/" className="text-lg font-extrabold tracking-tight">FRAME</Link>
          <nav className="flex gap-1">
            {ITEMS.slice(0, 4).map((it) => (
              <Link key={it.href} href={it.href}
                className="rounded-md px-3 py-1.5 text-sm font-medium text-tx3 hover:text-tx">
                {it.label}
              </Link>
            ))}
          </nav>
          <button className="ml-auto rounded-md bg-white px-4 py-2 text-sm font-semibold text-black">
            로그인
          </button>
        </div>
      </header>

      {/* mobile bottom tab */}
      <nav className="fixed inset-x-0 bottom-0 z-20 flex border-t border-line bg-black pb-5 pt-2 md:hidden">
        {ITEMS.map((it) => {
          const Icon = it.icon;
          return (
            <Link key={it.href} href={it.href}
              className="flex flex-1 flex-col items-center gap-0.5 text-[10px] text-tx3">
              <Icon size={18} />
              {it.label}
            </Link>
          );
        })}
      </nav>
    </>
  );
}
```

- [ ] **Step 4: Wire `Nav` into `web/src/app/layout.tsx`**

Import and render `<Nav />` above `{children}`, and add bottom padding on mobile so the tab bar doesn't cover content:
```tsx
import { Nav } from "@/components/Nav";
import "./globals.css";

export const metadata = { title: "FRAME — 전시 디스커버리", description: "사진·영상 전시를 찾고 둘러보세요" };

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="ko">
      <body>
        <Nav />
        <div className="pb-24 md:pb-0">{children}</div>
      </body>
    </html>
  );
}
```

- [ ] **Step 5: Run test + dev server**

Run: `npm run test -- Nav` → PASS.
Run: `npm run dev`, open http://localhost:3000, resize the window: desktop shows top nav, narrow shows bottom tab. Stop server.

- [ ] **Step 6: Commit**

```bash
git add web/src
git commit -m "feat(web): responsive nav (top nav / bottom tab)"
```

---

## Task 7: 둘러보기 home — time mode

**Files:**
- Create: `web/src/components/FilterChips.tsx`
- Modify: `web/src/app/page.tsx`
- Test: `web/src/components/FilterChips.test.tsx`

- [ ] **Step 1: Write the failing test for FilterChips**

```tsx
// web/src/components/FilterChips.test.tsx
import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { FilterChips } from "@/components/FilterChips";

describe("FilterChips", () => {
  it("toggles a chip and reports the change", () => {
    const onToggle = vi.fn();
    render(<FilterChips options={[{ value: "ongoing", label: "진행중" }]} active={[]} onToggle={onToggle} />);
    fireEvent.click(screen.getByText("진행중"));
    expect(onToggle).toHaveBeenCalledWith("ongoing");
  });
  it("marks active chips", () => {
    render(<FilterChips options={[{ value: "free", label: "무료" }]} active={["free"]} onToggle={() => {}} />);
    expect(screen.getByText("무료")).toHaveClass("bg-white");
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `npm run test -- FilterChips`
Expected: FAIL — cannot find `@/components/FilterChips`.

- [ ] **Step 3: Write FilterChips**

```tsx
// web/src/components/FilterChips.tsx
"use client";

export interface ChipOption { value: string; label: string; }

export function FilterChips({
  options, active, onToggle,
}: { options: ChipOption[]; active: string[]; onToggle: (value: string) => void }) {
  return (
    <div className="flex flex-wrap gap-2">
      {options.map((o) => {
        const on = active.includes(o.value);
        return (
          <button key={o.value} type="button" onClick={() => onToggle(o.value)}
            className={`rounded-full px-3.5 py-1.5 text-[13px] font-medium transition ${
              on ? "border border-white bg-white font-semibold text-black"
                 : "border border-line text-tx2 hover:text-tx"}`}>
            {o.label}
          </button>
        );
      })}
    </div>
  );
}
```

- [ ] **Step 4: Build the home page (time mode)**

Replace `web/src/app/page.tsx`. It is a client component that loads the catalog, shows the header counts, status FilterChips, a featured block, "곧 종료" row, and "진행 중" grid. Include a 타임/스와이프 segment toggle (swipe view added in Task 8 — for now the스와이프 button can route to `/?mode=swipe` and render the deck once Task 8 lands; in this task it can be a disabled-looking placeholder).

```tsx
// web/src/app/page.tsx
"use client";
import { useMemo, useState } from "react";
import { loadCatalogSync } from "@/lib/catalogClient";
import { applyFilters, type FilterState } from "@/lib/filters";
import { isClosingSoon } from "@/lib/status";
import { ExhibitionCard } from "@/components/ExhibitionCard";
import { FilterChips } from "@/components/FilterChips";

const STATUS_OPTS = [
  { value: "ongoing", label: "진행중" },
  { value: "closing", label: "곧 종료" },
  { value: "upcoming", label: "예정" },
];
const EXTRA_OPTS = [
  { value: "free", label: "무료" },
  { value: "photo", label: "사진" },
  { value: "solo", label: "개인전" },
];

export default function Home() {
  const catalog = loadCatalogSync();
  const today = new Date();
  const [chips, setChips] = useState<string[]>([]);
  const toggle = (v: string) => setChips((c) => (c.includes(v) ? c.filter((x) => x !== v) : [...c, v]));

  const f: FilterState = useMemo(() => ({
    statuses: chips.filter((c) => ["ongoing", "upcoming"].includes(c)) as FilterState["statuses"],
    mediums: chips.includes("photo") ? ["photo"] : [],
    types: chips.includes("solo") ? ["solo"] : [],
    freeOnly: chips.includes("free"),
    regions: [],
  }), [chips]);

  let list = applyFilters(catalog.exhibitions, f);
  if (chips.includes("closing")) list = list.filter((e) => isClosingSoon(e.endDate, today));

  const featured = catalog.exhibitions.find((e) => e.featured) ?? catalog.exhibitions[0];
  const closingSoon = catalog.exhibitions
    .filter((e) => e.status === "ongoing" && isClosingSoon(e.endDate, today))
    .sort((a, b) => (a.endDate ?? "").localeCompare(b.endDate ?? ""));
  const ongoing = list.filter((e) => e.status === "ongoing");

  const counts = {
    ongoing: catalog.exhibitions.filter((e) => e.status === "ongoing").length,
    closing: closingSoon.length,
    upcoming: catalog.exhibitions.filter((e) => e.status === "upcoming").length,
  };

  return (
    <main className="mx-auto max-w-[1180px] px-7">
      <div className="py-10">
        <div className="text-xs font-semibold uppercase tracking-wide text-tx3">
          {today.toISOString().slice(0, 10)} · 서울
        </div>
        <h1 className="mt-2.5 text-[38px] font-extrabold leading-none tracking-tight">지금 볼 수 있는 전시</h1>
        <p className="mt-3 text-sm text-tx2">
          진행 중 <b className="text-tx">{counts.ongoing}</b> · 이번 주 종료{" "}
          <b className="text-tx">{counts.closing}</b> · 곧 개막 <b className="text-tx">{counts.upcoming}</b>
        </p>
      </div>

      <div className="pb-7"><FilterChips options={[...STATUS_OPTS, ...EXTRA_OPTS]} active={chips} onToggle={toggle} /></div>

      {featured && (
        <section className="mb-9 grid overflow-hidden rounded border border-line md:grid-cols-[1.1fr_0.9fr]">
          <div className="relative min-h-[320px]">
            <ExhibitionCardHero e={featured} />
          </div>
        </section>
      )}

      {closingSoon.length > 0 && (
        <Section title="곧 종료" hint="놓치기 전에">
          {closingSoon.slice(0, 4).map((e) => <ExhibitionCard key={e.id} exhibition={e} today={today} />)}
        </Section>
      )}
      <Section title="진행 중" hint="지금 열려 있는">
        {ongoing.map((e) => <ExhibitionCard key={e.id} exhibition={e} today={today} />)}
      </Section>
    </main>
  );
}

function Section({ title, hint, children }: { title: string; hint: string; children: React.ReactNode }) {
  return (
    <section className="pb-11">
      <div className="mb-4 flex items-baseline gap-3">
        <h3 className="text-lg font-bold tracking-tight">{title}</h3>
        <span className="text-[13px] text-tx3">{hint}</span>
      </div>
      <div className="grid grid-cols-2 gap-4 md:grid-cols-4">{children}</div>
    </section>
  );
}

import type { Exhibition } from "@/lib/catalog";
import Link from "next/link";
import { PosterImage } from "@/components/PosterImage";
function ExhibitionCardHero({ e }: { e: Exhibition }) {
  return (
    <Link href={`/exhibitions/${e.id}`} className="absolute inset-0">
      <PosterImage src={e.posterImageUrl} alt={e.title} />
      <div className="absolute inset-x-0 bottom-0 bg-gradient-to-t from-black/90 to-transparent p-6">
        <div className="text-[11px] font-semibold uppercase tracking-widest text-tx2">이달의 전시</div>
        <h2 className="mt-2 text-2xl font-extrabold tracking-tight">{e.title}</h2>
        <div className="mt-2 text-sm text-tx2">
          {e.venue?.name} · {e.startDate}–{e.endDate}
        </div>
      </div>
    </Link>
  );
}
```

- [ ] **Step 5: Add `loadCatalogSync` for client components**

```ts
// web/src/lib/catalogClient.ts
import data from "../../public/data/exhibitions.json";
import { parseCatalog, type Catalog } from "@/lib/catalog";

let cached: Catalog | null = null;
export function loadCatalogSync(): Catalog {
  if (!cached) cached = parseCatalog(data);
  return cached;
}
```
(Ensure `tsconfig.json` has `"resolveJsonModule": true` — create-next-app sets this; verify.)

- [ ] **Step 6: Run tests + dev server**

Run: `npm run test -- FilterChips` → PASS.
Run: `npm run dev`, open http://localhost:3000 — verify header counts, chips toggle visually, featured block, "곧 종료" with D-day badges, "진행 중" grid. Click a card → it should attempt to route to `/exhibitions/<id>` (404 until Task 10). Stop server.

- [ ] **Step 7: Commit**

```bash
git add web/src
git commit -m "feat(web): 둘러보기 home (time mode) + filter chips"
```

---

## Task 8: 스와이프 (E) mode

**Files:**
- Create: `web/src/components/SwipeDeck.tsx`
- Modify: `web/src/app/page.tsx` (segment toggle renders the deck)
- Test: `web/src/components/SwipeDeck.test.tsx`

- [ ] **Step 1: Write the failing test**

```tsx
// web/src/components/SwipeDeck.test.tsx
import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { SwipeDeck } from "@/components/SwipeDeck";
import type { Exhibition } from "@/lib/catalog";

function ex(id: string, title: string): Exhibition {
  return {
    id, title, titleEn: null, posterImageUrl: "https://x/p.jpg", description: null,
    medium: "photo", exhibitionType: "solo", genreTags: [], feeType: "free",
    priceMin: null, priceMax: null, startDate: null, endDate: null, status: "ongoing",
    openHours: null, venue: null, artists: [], sourceUrl: null, featured: false, popularityScore: null,
  };
}

describe("SwipeDeck", () => {
  it("advances to the next card on skip", () => {
    render(<SwipeDeck items={[ex("a", "첫번째"), ex("b", "두번째")]} />);
    expect(screen.getByText("첫번째")).toBeInTheDocument();
    fireEvent.click(screen.getByLabelText("넘기기"));
    expect(screen.getByText("두번째")).toBeInTheDocument();
  });
  it("shows end state when exhausted", () => {
    render(<SwipeDeck items={[ex("a", "유일")]} />);
    fireEvent.click(screen.getByLabelText("넘기기"));
    expect(screen.getByText(/모두 둘러봤어요/)).toBeInTheDocument();
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `npm run test -- SwipeDeck`
Expected: FAIL — cannot find `@/components/SwipeDeck`.

- [ ] **Step 3: Write SwipeDeck**

```tsx
// web/src/components/SwipeDeck.tsx
"use client";
import { useState } from "react";
import { X, Heart, Share2 } from "lucide-react";
import { PosterImage } from "@/components/PosterImage";
import { StatusBadge } from "@/components/StatusBadge";
import type { Exhibition } from "@/lib/catalog";

export function SwipeDeck({ items }: { items: Exhibition[] }) {
  const [i, setI] = useState(0);
  const current = items[i];
  if (!current) {
    return <div className="flex min-h-[60vh] items-center justify-center text-tx3">모두 둘러봤어요</div>;
  }
  return (
    <div className="relative mx-auto h-[70vh] max-w-md">
      <div className="absolute inset-0 overflow-hidden rounded-2xl border border-line">
        <PosterImage src={current.posterImageUrl} alt={current.title} />
        <div className="absolute inset-0 bg-gradient-to-t from-black/90 via-transparent" />
        <div className="absolute left-5 top-5"><StatusBadge e={current} /></div>
        <div className="absolute inset-x-0 bottom-24 px-6">
          <h2 className="text-3xl font-extrabold tracking-tight">{current.title}</h2>
          <div className="mt-2 text-sm text-tx2">{current.venue?.name ?? "장소 미정"}</div>
        </div>
      </div>
      <div className="absolute inset-x-0 bottom-5 flex justify-center gap-4">
        <button aria-label="넘기기" onClick={() => setI((n) => n + 1)}
          className="flex h-14 w-14 items-center justify-center rounded-full border border-line2 bg-black/50 text-white">
          <X size={20} />
        </button>
        <button aria-label="스크랩" onClick={() => setI((n) => n + 1)}
          className="flex h-16 w-16 items-center justify-center rounded-full bg-white text-black">
          <Heart size={22} />
        </button>
        <button aria-label="공유"
          className="flex h-14 w-14 items-center justify-center rounded-full border border-line2 bg-black/50 text-white">
          <Share2 size={18} />
        </button>
      </div>
    </div>
  );
}
```

- [ ] **Step 4: Wire the segment toggle in `page.tsx`**

Add `const [mode, setMode] = useState<"time" | "swipe">("time")`, render a two-button segment (타임 / 스와이프) styled like the mockup (active = white bg/black text), and when `mode === "swipe"` render `<SwipeDeck items={ongoing} />` instead of the featured/sections block.

- [ ] **Step 5: Run test + browser**

Run: `npm run test -- SwipeDeck` → PASS.
Run: `npm run dev`, toggle to 스와이프, click ✕/♡ to advance, verify end state. Stop server.

- [ ] **Step 6: Commit**

```bash
git add web/src
git commit -m "feat(web): swipe discovery mode"
```

---

## Task 9: 검색 / 필터 page

**Files:**
- Create: `web/src/app/search/page.tsx`

- [ ] **Step 1: Build the search page**

Client component: a text input bound to `searchExhibitions`, plus `FilterChips` for status/medium/type/free and a region chip set derived from the catalog venues. Render results in the same 4-col grid using `ExhibitionCard`. Show a result count and an empty state ("조건에 맞는 전시가 없어요").

```tsx
// web/src/app/search/page.tsx
"use client";
import { useMemo, useState } from "react";
import { Search } from "lucide-react";
import { loadCatalogSync } from "@/lib/catalogClient";
import { applyFilters, searchExhibitions, type FilterState } from "@/lib/filters";
import { ExhibitionCard } from "@/components/ExhibitionCard";
import { FilterChips } from "@/components/FilterChips";

export default function SearchPage() {
  const catalog = loadCatalogSync();
  const [q, setQ] = useState("");
  const [chips, setChips] = useState<string[]>([]);
  const toggle = (v: string) => setChips((c) => (c.includes(v) ? c.filter((x) => x !== v) : [...c, v]));

  const regions = useMemo(
    () => Array.from(new Set(catalog.venues.map((v) => v.region).filter(Boolean))) as string[],
    [catalog.venues],
  );

  const f: FilterState = {
    statuses: chips.filter((c) => ["ongoing", "upcoming", "past"].includes(c)) as FilterState["statuses"],
    mediums: chips.filter((c) => ["photo", "video", "gear"].includes(c)),
    types: chips.filter((c) => ["solo", "group", "curated"].includes(c)),
    freeOnly: chips.includes("free"),
    regions: chips.filter((c) => regions.includes(c)),
  };
  const results = searchExhibitions(applyFilters(catalog.exhibitions, f), q);

  return (
    <main className="mx-auto max-w-[1180px] px-7 py-8">
      <div className="mb-5 flex items-center gap-2 rounded-lg border border-line px-3 py-2.5">
        <Search size={16} className="text-tx3" />
        <input value={q} onChange={(e) => setQ(e.target.value)} placeholder="전시 · 작가 · 장소"
          className="w-full bg-transparent text-sm outline-none placeholder:text-tx3" />
      </div>
      <div className="mb-3"><FilterChips active={chips} onToggle={toggle} options={[
        { value: "ongoing", label: "진행중" }, { value: "upcoming", label: "예정" }, { value: "past", label: "종료" },
        { value: "photo", label: "사진" }, { value: "video", label: "영상" }, { value: "gear", label: "장비" },
        { value: "solo", label: "개인전" }, { value: "group", label: "단체전" }, { value: "free", label: "무료" },
        ...regions.map((r) => ({ value: r, label: r })),
      ]} /></div>
      <div className="mb-4 text-sm text-tx3">{results.length}건</div>
      {results.length === 0 ? (
        <div className="py-20 text-center text-tx3">조건에 맞는 전시가 없어요</div>
      ) : (
        <div className="grid grid-cols-2 gap-4 md:grid-cols-4">
          {results.map((e) => <ExhibitionCard key={e.id} exhibition={e} />)}
        </div>
      )}
    </main>
  );
}
```

- [ ] **Step 2: Browser verify**

Run: `npm run dev`, open http://localhost:3000/search — type a query, toggle chips, confirm result count and grid update; clear everything → all items; nonsense query → empty state. Stop server.

- [ ] **Step 3: Commit**

```bash
git add web/src/app/search
git commit -m "feat(web): search + filter page"
```

---

## Task 10: 전시 상세 page

**Files:**
- Create: `web/src/app/exhibitions/[id]/page.tsx`

- [ ] **Step 1: Build the detail page**

Server component using `generateStaticParams` over the catalog so each exhibition is statically rendered. Layout: large poster (left/top), title + venue + dates + fee + medium/type + artists + description, a 스크랩 button, a "원문 보기" link to `sourceUrl`, and a small static map placeholder (full MapLibre mini-map can be added when `MapView` exists in Task 11 — here, render venue name + address text; if `venue.lat/lng` exist, embed a single-pin `MapView` with `height=240`).

```tsx
// web/src/app/exhibitions/[id]/page.tsx
import { notFound } from "next/navigation";
import { loadCatalog } from "@/lib/catalog";
import { PosterImage } from "@/components/PosterImage";
import { ScrapButton } from "@/components/ScrapButton";
import { ddayLabel } from "@/lib/status";

export async function generateStaticParams() {
  const cat = await loadCatalog();
  return cat.exhibitions.map((e) => ({ id: e.id }));
}

export default async function ExhibitionDetail({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  const cat = await loadCatalog();
  const e = cat.exhibitions.find((x) => x.id === id);
  if (!e) notFound();

  const dday = ddayLabel(e.endDate);
  return (
    <main className="mx-auto max-w-[1100px] px-7 py-8">
      <div className="grid gap-8 md:grid-cols-[420px_1fr]">
        <div className="relative aspect-[3/4] overflow-hidden rounded border border-line">
          <PosterImage src={e.posterImageUrl} alt={e.title} />
        </div>
        <div>
          <div className="text-[11px] font-semibold uppercase tracking-widest text-tx3">
            {[e.medium, e.exhibitionType].filter(Boolean).join(" · ")}
          </div>
          <h1 className="mt-3 text-3xl font-extrabold tracking-tight">{e.title}</h1>
          {e.titleEn && <div className="mt-1 text-tx2">{e.titleEn}</div>}
          <div className="mt-5 space-y-1.5 text-sm">
            <div><span className="text-tx3">장소</span>  {e.venue?.name ?? "미정"}{e.venue?.district ? ` · ${e.venue.district}` : ""}</div>
            <div><span className="text-tx3">기간</span>  {e.startDate} – {e.endDate} {dday && <span className="ml-2 rounded-full bg-white px-2 py-0.5 text-[11px] font-bold text-black">{dday}</span>}</div>
            <div><span className="text-tx3">요금</span>  {e.feeType === "free" ? "무료" : e.priceMin ? `${e.priceMin.toLocaleString()}원~` : "유료"}</div>
            {e.artists.length > 0 && <div><span className="text-tx3">작가</span>  {e.artists.map((a) => a.name).join(", ")}</div>}
            {e.openHours && <div><span className="text-tx3">관람</span>  {e.openHours}</div>}
          </div>
          {e.description && <p className="mt-6 whitespace-pre-line text-[14px] leading-relaxed text-tx2">{e.description}</p>}
          <div className="mt-7 flex items-center gap-3">
            <ScrapButton />
            {e.sourceUrl && (
              <a href={e.sourceUrl} target="_blank" rel="noopener noreferrer"
                className="rounded-lg border border-line2 px-4 py-2 text-sm font-medium hover:bg-panel2">
                원문 보기
              </a>
            )}
          </div>
        </div>
      </div>
    </main>
  );
}
```

- [ ] **Step 2: Browser verify**

Run: `npm run dev`, click a card on the home page → detail renders with poster, metadata, D-day, description, 원문 보기. Visit a bad id `/exhibitions/nope` → 404. Stop server.

- [ ] **Step 3: Commit**

```bash
git add web/src/app/exhibitions
git commit -m "feat(web): exhibition detail page (static)"
```

---

## Task 11: 지도 page (MapLibre)

**Files:**
- Create: `web/src/components/MapView.tsx`, `web/src/lib/regions.ts`, `web/src/app/map/page.tsx`
- Test: `web/src/lib/regions.test.ts`
- Deps: `npm i maplibre-gl`

- [ ] **Step 1: Write the failing test for region grouping**

```ts
// web/src/lib/regions.test.ts
import { describe, expect, it } from "vitest";
import { groupByRegion } from "@/lib/regions";
import type { Exhibition } from "@/lib/catalog";

function ex(id: string, region: string | null, lat: number | null): Exhibition {
  return {
    id, title: id, titleEn: null, posterImageUrl: null, description: null, medium: null,
    exhibitionType: null, genreTags: [], feeType: null, priceMin: null, priceMax: null,
    startDate: null, endDate: null, status: "ongoing", openHours: null,
    venue: region || lat ? { id: "v", name: "v", region, district: null, lat, lng: lat } : null,
    artists: [], sourceUrl: null, featured: false, popularityScore: null,
  };
}

describe("groupByRegion", () => {
  it("buckets exhibitions with coords by region, drops those without coords", () => {
    const groups = groupByRegion([ex("a", "서울", 37.5), ex("b", "서울", 37.6), ex("c", "부산", 35.1), ex("d", null, null)]);
    expect(groups.get("서울")?.length).toBe(2);
    expect(groups.get("부산")?.length).toBe(1);
    expect([...groups.keys()]).not.toContain(null);
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `npm run test -- regions`
Expected: FAIL — cannot find `@/lib/regions`.

- [ ] **Step 3: Write `regions.ts`**

```ts
// web/src/lib/regions.ts
import type { Exhibition } from "@/lib/catalog";

export function groupByRegion(list: Exhibition[]): Map<string, Exhibition[]> {
  const groups = new Map<string, Exhibition[]>();
  for (const e of list) {
    const region = e.venue?.region;
    if (!region || e.venue?.lat == null || e.venue?.lng == null) continue;
    const bucket = groups.get(region) ?? [];
    bucket.push(e);
    groups.set(region, bucket);
  }
  return groups;
}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `npm run test -- regions`
Expected: PASS.

- [ ] **Step 5: Write `MapView` (client, dynamic import of maplibre)**

```tsx
// web/src/components/MapView.tsx
"use client";
import { useEffect, useRef } from "react";
import maplibregl from "maplibre-gl";
import "maplibre-gl/dist/maplibre-gl.css";
import type { Exhibition } from "@/lib/catalog";

const STYLE = "https://demotiles.maplibre.org/style.json"; // free OSM-based; swap for a richer style later

export function MapView({ items, height = 480, onSelect }:
  { items: Exhibition[]; height?: number; onSelect?: (id: string) => void }) {
  const ref = useRef<HTMLDivElement>(null);
  useEffect(() => {
    if (!ref.current) return;
    const pts = items.filter((e) => e.venue?.lat != null && e.venue?.lng != null);
    const map = new maplibregl.Map({
      container: ref.current, style: STYLE,
      center: pts[0] ? [pts[0].venue!.lng!, pts[0].venue!.lat!] : [126.98, 37.57], zoom: 11,
    });
    for (const e of pts) {
      const el = document.createElement("button");
      el.className = "h-3 w-3 rounded-full border-2 border-white bg-black";
      el.setAttribute("aria-label", e.title);
      el.onclick = () => onSelect?.(e.id);
      new maplibregl.Marker({ element: el }).setLngLat([e.venue!.lng!, e.venue!.lat!]).addTo(map);
    }
    return () => map.remove();
  }, [items, onSelect]);
  return <div ref={ref} style={{ height }} className="w-full overflow-hidden rounded border border-line" />;
}
```

- [ ] **Step 6: Write the map page (map ↔ list sync)**

```tsx
// web/src/app/map/page.tsx
"use client";
import dynamic from "next/dynamic";
import { useMemo, useState } from "react";
import { loadCatalogSync } from "@/lib/catalogClient";
import { groupByRegion } from "@/lib/regions";
import { ExhibitionCard } from "@/components/ExhibitionCard";

const MapView = dynamic(() => import("@/components/MapView").then((m) => m.MapView), { ssr: false });

export default function MapPage() {
  const catalog = loadCatalogSync();
  const groups = useMemo(() => groupByRegion(catalog.exhibitions), [catalog.exhibitions]);
  const regions = [...groups.keys()];
  const [region, setRegion] = useState(regions[0] ?? "");
  const items = groups.get(region) ?? [];

  return (
    <main className="mx-auto max-w-[1180px] px-7 py-6">
      <div className="mb-4 flex flex-wrap gap-2">
        {regions.map((r) => (
          <button key={r} onClick={() => setRegion(r)}
            className={`rounded-full px-3.5 py-1.5 text-[13px] ${r === region ? "bg-white font-semibold text-black" : "border border-line text-tx2"}`}>
            {r} <span className="opacity-60">{groups.get(r)?.length}</span>
          </button>
        ))}
      </div>
      <div className="grid gap-5 md:grid-cols-[1fr_360px]">
        <MapView items={items} height={560} />
        <div className="grid grid-cols-2 gap-4 md:grid-cols-1">
          {items.map((e) => <ExhibitionCard key={e.id} exhibition={e} />)}
        </div>
      </div>
    </main>
  );
}
```

- [ ] **Step 7: Browser verify**

Run: `npm run dev`, open http://localhost:3000/map — map renders with pins, region chips switch the set + recenters, side list matches. Stop server.

- [ ] **Step 8: Commit**

```bash
git add web/src web/package.json web/package-lock.json
git commit -m "feat(web): map page (MapLibre) with region grouping + list sync"
```

---

## Task 12: PWA (manifest + service worker + offline catalog)

**Files:**
- Create: `web/public/manifest.webmanifest`, `web/public/icons/icon-192.png`, `web/public/icons/icon-512.png`
- Modify: `web/next.config.mjs`, `web/src/app/layout.tsx`
- Deps: `npm i @ducanh2912/next-pwa`

- [ ] **Step 1: Add the web manifest**

```json
// web/public/manifest.webmanifest
{
  "name": "FRAME — 전시 디스커버리",
  "short_name": "FRAME",
  "start_url": "/",
  "display": "standalone",
  "background_color": "#000000",
  "theme_color": "#000000",
  "icons": [
    { "src": "/icons/icon-192.png", "sizes": "192x192", "type": "image/png" },
    { "src": "/icons/icon-512.png", "sizes": "512x512", "type": "image/png", "purpose": "any maskable" }
  ]
}
```
Add the two PNG icons (solid black square with white "F" wordmark is fine as a placeholder; replace during polish). Reference the manifest + theme color in `layout.tsx` metadata:
```tsx
export const metadata = {
  title: "FRAME — 전시 디스커버리",
  description: "사진·영상 전시를 찾고 둘러보세요",
  manifest: "/manifest.webmanifest",
};
export const viewport = { themeColor: "#000000" };
```

- [ ] **Step 2: Wrap next config with next-pwa (caches app shell + catalog JSON)**

```js
// web/next.config.mjs
import withPWAInit from "@ducanh2912/next-pwa";

const withPWA = withPWAInit({
  dest: "public",
  disable: process.env.NODE_ENV === "development",
  workboxOptions: {
    runtimeCaching: [
      {
        urlPattern: /\/data\/exhibitions\.json$/,
        handler: "StaleWhileRevalidate",
        options: { cacheName: "catalog" },
      },
    ],
  },
});

/** @type {import('next').NextConfig} */
const nextConfig = { output: "export", images: { unoptimized: true } };
export default withPWA(nextConfig);
```
Note: `output: "export"` makes a static site (Vercel/static host). The exhibition detail pages are pre-rendered via `generateStaticParams` (Task 10). Client pages (home/search/map) work as static + client JS.

- [ ] **Step 3: Build and verify installability**

Run (from `web/`): `npm run build`
Expected: build succeeds, `out/` produced (static export). Run `npx serve out` (or `npm i -D serve`), open the served URL, and in Chrome DevTools → Application: a service worker is registered and the manifest is detected (install icon appears). Verify offline: load once, go offline (DevTools → Network → Offline), reload → app shell + catalog still render.

- [ ] **Step 4: Commit**

```bash
git add web
git commit -m "feat(web): PWA manifest + offline catalog caching"
```

---

## Task 13: CI — crawler exports catalog into the web app

**Files:**
- Create or modify the crawl GitHub Actions workflow under `.github/workflows/`

- [ ] **Step 1: Inspect the existing crawl workflow**

Run (repo root): `ls .github/workflows && sed -n '1,80p' .github/workflows/*crawl*.yml`
Identify where `crawler run-all` executes and how secrets (`SHEET_ID`, `GOOGLE_SERVICE_ACCOUNT_JSON`, `KAKAO_REST_API_KEY`) are provided.

- [ ] **Step 2: Add an export + commit step after the crawl**

In the crawl job, after `crawler run-all`, add:
```yaml
      - name: Export catalog JSON for web
        run: |
          python -m crawler.cli export-json --out web/public/data/exhibitions.json
        env:
          SHEET_ID: ${{ secrets.SHEET_ID }}
          GOOGLE_SERVICE_ACCOUNT_JSON: ${{ secrets.GOOGLE_SERVICE_ACCOUNT_JSON }}
      - name: Commit updated catalog
        run: |
          git config user.name "github-actions[bot]"
          git config user.email "github-actions[bot]@users.noreply.github.com"
          git add web/public/data/exhibitions.json
          git diff --staged --quiet || git commit -m "chore(data): refresh exhibitions.json [skip ci]"
          git push
```
(If the workflow entrypoint is `crawler` console-script rather than `python -m`, use `crawler export-json --out web/public/data/exhibitions.json`. Confirm from Step 1.)

- [ ] **Step 3: Validate workflow YAML**

Run: `python -c "import yaml,sys; yaml.safe_load(open([f for f in __import__('glob').glob('.github/workflows/*.yml')][0]))" ` for each changed file, or `npx --yes yaml-lint .github/workflows/*.yml`.
Expected: no parse errors.

- [ ] **Step 4: Commit**

```bash
git add .github/workflows
git commit -m "ci: export exhibitions.json to web/ after crawl"
```

---

## Self-Review (completed during planning)

**Spec coverage:**
- §3 design tone → Task 1 tokens, all components use BW + inversion accent, lucide icons (no emoji), polish noted.
- §4 IA & screens → 둘러보기/타임 (Task 7), 스와이프 (Task 8), 검색/필터 (Task 9), 상세 (Task 10), 지도 (Task 11), responsive nav incl. 스크랩/마이 entries (Task 6). 스크랩/마이 *pages* and login are Plan 3 — Nav links exist but routes 404 until then (acceptable for this plan's scope).
- §5.1 static JSON consumption → Tasks 2, 7, catalogClient. §5.3 MapLibre+OSM → Task 11. §9 PWA → Task 12. CI wiring → Task 13.

**Placeholder scan:** No TBD/TODO. `ScrapButton` is intentionally visual-only and labeled as such (wired in Plan 3). Sample `exhibitions.json` content is described with explicit shape (matches Task 2 `RAW`); the implementer fills realistic values — this is data, not a code placeholder.

**Type consistency:** `Exhibition`/`Venue`/`Catalog` shapes (camelCase) defined in Task 2 are used identically across filters (Task 4), components (Task 5), pages (7–11), regions (11). `FilterState` fields (`statuses, mediums, types, freeOnly, regions`) match between definition (Task 4) and all consumers (Tasks 7, 9). `loadCatalogSync` (client) vs `loadCatalog` (async, server detail/static params) are used in the correct contexts.

**Known follow-ups (not gaps):** richer MapLibre style/token; real PWA icons; 스크랩/마이 pages (Plan 3). The 상세 mini-map is optional in Task 10 and fully covered by `MapView` from Task 11 if desired.
