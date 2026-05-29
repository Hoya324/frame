# Subscriptions & Email Jobs — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Let users subscribe to email notifications (weekly digest, closing-soon reminders for their scraps, and custom-filter alerts) and deliver them via scheduled GitHub Actions cron jobs that read the static catalog snapshot + Supabase, sending through Resend with per-send dedupe.

**Architecture:** Two parts. (1) A subscription **settings UI** added to the 마이 page (Plan 3), persisting to a new `subscriptions` table (RLS, self-only). (2) A standalone Node/TypeScript **jobs** package (`jobs/`) run by GitHub Actions cron: it reads the committed catalog JSON (`web/public/data/exhibitions.json`) and Supabase using the **service role key** (bypasses RLS), matches recipients, sends emails through Resend, and records every send in an `email_log` table to prevent duplicates. All matching/dedupe logic is pure and unit-tested with Vitest; Supabase and Resend are injected so tests need no network.

**Tech Stack:** Supabase (Postgres + RLS, service role for jobs), Resend (`resend` SDK), Node 20 + TypeScript run via `tsx`, Vitest, GitHub Actions cron.

---

## Background for the implementer

- Builds on **Plan 2** (web app) and **Plan 3** (Supabase user plane: `profiles`, `bookmarks`, `AuthProvider`, `getSupabase`). Re-read spec `docs/superpowers/specs/2026-05-30-exhibition-site-design.md` §7 (DB model: `subscriptions`, `email_log`) and §8 (email system) before starting.
- **Contracts to reuse, not redefine:**
  - The catalog JSON snapshot at `web/public/data/exhibitions.json` (Plan 1 shape; snake_case keys: `id`, `title`, `medium`, `start_date`, `end_date`, `status`, `venue.region`, `artists[].name`, `genre_tags`, `source_url`, `poster_image_url`).
  - Web client Supabase (`web/src/lib/supabase.ts` → `getSupabase`) and `AuthProvider`/`useAuth` from Plan 3.
  - Design tokens (BW tone), `lucide-react` icons.
- **Two Supabase access modes:** the **web app** uses the anon key + RLS (user can only touch their own rows). The **jobs** use the **service role key** (server-only secret, full access) so they can read every subscriber's rows. The service role key must NEVER ship to the browser — it lives only in GitHub Actions secrets and `jobs/.env` (gitignored).
- **Dedupe model:** `email_log(user_id, type, ref)` is unique. Before sending, a job checks the log; after sending it records the ref. `ref` differs per job type (weekly: ISO-week string; closing-soon: `exhibitionId:dday`; custom: `exhibitionId`). This makes every job idempotent and safe to re-run.
- **"New" for custom alerts** is defined implicitly by the dedupe log: the first time a catalog exhibition matches a user's filters, it is sent and logged by `exhibitionId`; later runs skip it. No separate "first-seen" field is needed.
- The jobs read the **committed snapshot** (refreshed daily by the crawl workflow from Plan 2 Task 13), so they run after the catalog is up to date.

## File Structure

```
supabase/
  migrations/0002_subscriptions_email.sql   # subscriptions + email_log + RLS
web/
  src/
    lib/subscriptions.ts                     # web data layer (get/upsert) — anon client
    lib/subscriptions.test.ts
    components/SubscriptionSettings.tsx       # toggles + custom filter chips, used in 마이
    app/me/page.tsx                           # MODIFIED: mount SubscriptionSettings
jobs/
  package.json, tsconfig.json, vitest.config.ts
  .env.example
  src/
    lib/env.ts            # required env loader
    lib/supabaseAdmin.ts  # service-role client
    lib/catalog.ts        # read + type the snapshot
    lib/match.ts          # PURE: closing-soon selection, custom-filter match  (tested)
    lib/emailLog.ts       # alreadySent / recordSent over a client            (tested)
    lib/resendClient.ts   # send wrapper (injectable)
    lib/render.ts         # email HTML templates
    weekly-digest.ts      # entry: weekly digest
    closing-soon.ts       # entry: closing-soon reminders (daily)
    custom-alerts.ts      # entry: custom-filter alerts (daily)
.github/workflows/
  emails-weekly.yml
  emails-daily.yml
```

---

## Task 1: Subscriptions + email_log schema

**Files:**
- Create: `supabase/migrations/0002_subscriptions_email.sql`

- [ ] **Step 1: Write the migration SQL**

```sql
-- supabase/migrations/0002_subscriptions_email.sql
-- Subscriptions + email send log for the FRAME notification system.

-- subscriptions: one row per (user, type). filters used only by 'custom'.
create table if not exists public.subscriptions (
  user_id uuid not null references auth.users(id) on delete cascade,
  type text not null check (type in ('weekly_digest', 'closing_soon', 'custom')),
  enabled boolean not null default true,
  filters jsonb not null default '{}'::jsonb,  -- { artists:[], regions:[], genres:[], mediums:[] }
  updated_at timestamptz not null default now(),
  primary key (user_id, type)
);

-- email_log: dedupe + audit. ref scopes a single logical send within a type.
create table if not exists public.email_log (
  user_id uuid not null references auth.users(id) on delete cascade,
  type text not null,
  ref text not null,
  sent_at timestamptz not null default now(),
  primary key (user_id, type, ref)
);

create index if not exists email_log_user_type_idx on public.email_log (user_id, type);

-- RLS. The web app (anon key) only touches the caller's own subscriptions.
-- Jobs use the service role key, which bypasses RLS entirely.
alter table public.subscriptions enable row level security;
alter table public.email_log enable row level security;

drop policy if exists "subs self all" on public.subscriptions;
create policy "subs self all" on public.subscriptions
  for all using (auth.uid() = user_id) with check (auth.uid() = user_id);

-- email_log: users may read their own log; no client writes (jobs write via service role).
drop policy if exists "email_log self read" on public.email_log;
create policy "email_log self read" on public.email_log
  for select using (auth.uid() = user_id);
```

- [ ] **Step 2: Apply in Supabase**

Supabase → SQL Editor → paste → Run. Expect two new tables with RLS enabled. Also note the **service role key** (Project Settings → API → `service_role` secret) for later — it is required by the jobs.

- [ ] **Step 3: Commit**

```bash
git add supabase/migrations/0002_subscriptions_email.sql
git commit -m "feat(db): subscriptions + email_log schema with RLS"
```

---

## Task 2: Web subscriptions data layer

**Files:**
- Create: `web/src/lib/subscriptions.ts`
- Test: `web/src/lib/subscriptions.test.ts`

(Runs from `web/`. Mirrors the `bookmarks.ts` fake-client pattern from Plan 3.)

- [ ] **Step 1: Write the failing test**

```ts
// web/src/lib/subscriptions.test.ts
import { describe, expect, it, vi } from "vitest";
import { getSubscriptions, upsertSubscription, type SubType } from "@/lib/subscriptions";

function fakeClient(rows: any[] = []) {
  const eqSel = vi.fn().mockResolvedValue({ data: rows, error: null });
  const select = vi.fn(() => ({ eq: eqSel }));
  const upsert = vi.fn().mockResolvedValue({ error: null });
  const from = vi.fn(() => ({ select, upsert }));
  return { client: { from } as any, from, select, eqSel, upsert };
}

describe("subscriptions data layer", () => {
  it("getSubscriptions returns rows keyed by type", async () => {
    const f = fakeClient([
      { user_id: "u1", type: "weekly_digest", enabled: true, filters: {} },
      { user_id: "u1", type: "custom", enabled: false, filters: { regions: ["서울"] } },
    ]);
    const map = await getSubscriptions(f.client, "u1");
    expect(f.from).toHaveBeenCalledWith("subscriptions");
    expect(f.eqSel).toHaveBeenCalledWith("user_id", "u1");
    expect(map.weekly_digest?.enabled).toBe(true);
    expect(map.custom?.filters.regions).toEqual(["서울"]);
  });

  it("upsertSubscription writes a full row", async () => {
    const f = fakeClient();
    const type: SubType = "closing_soon";
    await upsertSubscription(f.client, "u1", type, true, {});
    expect(f.upsert).toHaveBeenCalledWith(
      { user_id: "u1", type: "closing_soon", enabled: true, filters: {} },
      { onConflict: "user_id,type" },
    );
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `npm run test -- subscriptions`
Expected: FAIL — cannot find `@/lib/subscriptions`.

- [ ] **Step 3: Write the implementation**

```ts
// web/src/lib/subscriptions.ts
import type { SupabaseClient } from "@supabase/supabase-js";

export type SubType = "weekly_digest" | "closing_soon" | "custom";
export interface CustomFilters {
  artists?: string[];
  regions?: string[];
  genres?: string[];
  mediums?: string[];
}
export interface Subscription {
  type: SubType;
  enabled: boolean;
  filters: CustomFilters;
}
export type SubscriptionMap = Partial<Record<SubType, Subscription>>;

export async function getSubscriptions(client: SupabaseClient, userId: string): Promise<SubscriptionMap> {
  const { data, error } = await client
    .from("subscriptions")
    .select("type, enabled, filters")
    .eq("user_id", userId);
  if (error) throw error;
  const map: SubscriptionMap = {};
  for (const r of data ?? []) {
    map[r.type as SubType] = { type: r.type, enabled: r.enabled, filters: r.filters ?? {} };
  }
  return map;
}

export async function upsertSubscription(
  client: SupabaseClient,
  userId: string,
  type: SubType,
  enabled: boolean,
  filters: CustomFilters = {},
): Promise<void> {
  const { error } = await client
    .from("subscriptions")
    .upsert({ user_id: userId, type, enabled, filters }, { onConflict: "user_id,type" });
  if (error) throw error;
}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `npm run test -- subscriptions`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add web/src/lib/subscriptions.ts web/src/lib/subscriptions.test.ts
git commit -m "feat(web): subscriptions data layer (get/upsert)"
```

---

## Task 3: Subscription settings UI in 마이

**Files:**
- Create: `web/src/components/SubscriptionSettings.tsx`
- Modify: `web/src/app/me/page.tsx` (replace the "구독 설정 — 곧 제공" stub from Plan 3)

- [ ] **Step 1: Build `SubscriptionSettings`**

Client component. On mount (when `user` exists) loads subscriptions via `getSubscriptions(getSupabase(), user.id)`. Renders three rows with toggle switches: 주간 다이제스트 (`weekly_digest`), 종료 임박 알림 (`closing_soon`), 맞춤 알림 (`custom`). When 맞춤 is enabled, show `FilterChips` (reused from Plan 2) for regions/mediums/genres derived from the catalog, persisting into `filters`. Each change calls `upsertSubscription` (optimistic local state).

```tsx
// web/src/components/SubscriptionSettings.tsx
"use client";
import { useEffect, useMemo, useState } from "react";
import { getSupabase } from "@/lib/supabase";
import { useAuth } from "@/components/AuthProvider";
import {
  getSubscriptions, upsertSubscription,
  type CustomFilters, type SubscriptionMap, type SubType,
} from "@/lib/subscriptions";
import { loadCatalogSync } from "@/lib/catalogClient";
import { FilterChips } from "@/components/FilterChips";

const ROWS: { type: SubType; label: string; desc: string }[] = [
  { type: "weekly_digest", label: "주간 다이제스트", desc: "매주 새로/진행 중인 전시 모음" },
  { type: "closing_soon", label: "종료 임박 알림", desc: "스크랩한 전시가 곧 끝날 때 (D-3, D-1)" },
  { type: "custom", label: "맞춤 알림", desc: "관심 조건에 맞는 새 전시" },
];

export function SubscriptionSettings() {
  const { user } = useAuth();
  const catalog = loadCatalogSync();
  const [subs, setSubs] = useState<SubscriptionMap>({});
  const [loaded, setLoaded] = useState(false);

  useEffect(() => {
    if (!user) return;
    getSubscriptions(getSupabase(), user.id)
      .then((m) => { setSubs(m); setLoaded(true); })
      .catch(() => setLoaded(true));
  }, [user]);

  const regions = useMemo(
    () => Array.from(new Set(catalog.venues.map((v) => v.region).filter(Boolean))) as string[],
    [catalog.venues],
  );
  const mediums = ["photo", "video", "gear"];

  async function setEnabled(type: SubType, enabled: boolean) {
    const prev = subs[type];
    const filters = prev?.filters ?? {};
    setSubs((s) => ({ ...s, [type]: { type, enabled, filters } }));
    if (user) await upsertSubscription(getSupabase(), user.id, type, enabled, filters);
  }

  async function setFilters(type: SubType, filters: CustomFilters) {
    const enabled = subs[type]?.enabled ?? true;
    setSubs((s) => ({ ...s, [type]: { type, enabled, filters } }));
    if (user) await upsertSubscription(getSupabase(), user.id, type, enabled, filters);
  }

  if (!user) return null;

  const custom = subs.custom;
  const toggleFilter = (key: keyof CustomFilters, value: string) => {
    const cur = custom?.filters[key] ?? [];
    const next = cur.includes(value) ? cur.filter((v) => v !== value) : [...cur, value];
    setFilters("custom", { ...(custom?.filters ?? {}), [key]: next });
  };

  return (
    <div className="rounded-lg border border-line p-5">
      <div className="text-sm text-tx3">구독 설정</div>
      <div className="mt-4 space-y-4">
        {ROWS.map((row) => {
          const on = subs[row.type]?.enabled ?? false;
          return (
            <div key={row.type}>
              <div className="flex items-center justify-between">
                <div>
                  <div className="text-sm font-medium">{row.label}</div>
                  <div className="text-xs text-tx3">{row.desc}</div>
                </div>
                <button
                  role="switch" aria-checked={on} aria-label={row.label}
                  onClick={() => void setEnabled(row.type, !on)}
                  disabled={!loaded}
                  className={`relative h-6 w-11 rounded-full transition ${on ? "bg-white" : "bg-panel2 border border-line"}`}
                >
                  <span className={`absolute top-0.5 h-5 w-5 rounded-full transition ${on ? "left-[22px] bg-black" : "left-0.5 bg-tx2"}`} />
                </button>
              </div>
              {row.type === "custom" && on && (
                <div className="mt-3 space-y-2 pl-1">
                  <div className="text-xs text-tx3">지역</div>
                  <FilterChips options={regions.map((r) => ({ value: r, label: r }))}
                    active={custom?.filters.regions ?? []} onToggle={(v) => toggleFilter("regions", v)} />
                  <div className="text-xs text-tx3">매체</div>
                  <FilterChips
                    options={[{ value: "photo", label: "사진" }, { value: "video", label: "영상" }, { value: "gear", label: "장비" }]}
                    active={custom?.filters.mediums ?? []} onToggle={(v) => toggleFilter("mediums", v)} />
                </div>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}
```

- [ ] **Step 2: Mount it in `me/page.tsx`**

In `web/src/app/me/page.tsx`, replace the placeholder block:
```tsx
<div className="mt-4 rounded-lg border border-line p-5 text-sm text-tx3">
  구독 설정 — 곧 제공
</div>
```
with:
```tsx
<div className="mt-4"><SubscriptionSettings /></div>
```
and add the import at the top: `import { SubscriptionSettings } from "@/components/SubscriptionSettings";`

- [ ] **Step 3: Browser verify**

Run (from `web/`): `npm run dev`, log in, open http://localhost:3000/me → three toggles; flip them and reload → state persists; enable 맞춤 → region/medium chips appear and persist. Verify in Supabase Table Editor that `subscriptions` rows are written. Stop server.

- [ ] **Step 4: Commit**

```bash
git add web/src/components/SubscriptionSettings.tsx web/src/app/me/page.tsx
git commit -m "feat(web): subscription settings UI in my page"
```

---

## Task 4: Jobs package scaffold

**Files:**
- Create: `jobs/package.json`, `jobs/tsconfig.json`, `jobs/vitest.config.ts`, `jobs/.env.example`, `jobs/.gitignore`, `jobs/src/lib/env.ts`

- [ ] **Step 1: Create `jobs/package.json`**

```json
{
  "name": "frame-jobs",
  "private": true,
  "type": "module",
  "scripts": {
    "weekly-digest": "tsx src/weekly-digest.ts",
    "closing-soon": "tsx src/closing-soon.ts",
    "custom-alerts": "tsx src/custom-alerts.ts",
    "test": "vitest run"
  },
  "dependencies": {
    "@supabase/supabase-js": "^2",
    "resend": "^4"
  },
  "devDependencies": {
    "tsx": "^4",
    "typescript": "^5",
    "vitest": "^2"
  }
}
```
Run (from `jobs/`): `npm install`.

- [ ] **Step 2: Create `jobs/tsconfig.json`**

```json
{
  "compilerOptions": {
    "target": "ES2022",
    "module": "ES2022",
    "moduleResolution": "Bundler",
    "strict": true,
    "esModuleInterop": true,
    "skipLibCheck": true,
    "resolveJsonModule": true,
    "noEmit": true
  },
  "include": ["src"]
}
```

- [ ] **Step 3: Create `jobs/vitest.config.ts`**

```ts
import { defineConfig } from "vitest/config";
export default defineConfig({ test: { environment: "node", globals: true } });
```

- [ ] **Step 4: Create `jobs/.env.example` and `jobs/.gitignore`**

`.env.example`:
```
SUPABASE_URL=https://YOUR-PROJECT.supabase.co
SUPABASE_SERVICE_ROLE_KEY=YOUR-SERVICE-ROLE-KEY
RESEND_API_KEY=re_xxx
EMAIL_FROM=FRAME <notify@yourdomain.com>
SITE_URL=https://your-frame-site.example
```
`.gitignore`:
```
node_modules
.env
```

- [ ] **Step 5: Create the env loader `jobs/src/lib/env.ts`**

```ts
// jobs/src/lib/env.ts
function required(name: string): string {
  const v = process.env[name];
  if (!v) throw new Error(`Missing required env var: ${name}`);
  return v;
}

export const env = {
  supabaseUrl: () => required("SUPABASE_URL"),
  supabaseServiceKey: () => required("SUPABASE_SERVICE_ROLE_KEY"),
  resendApiKey: () => required("RESEND_API_KEY"),
  emailFrom: () => required("EMAIL_FROM"),
  siteUrl: () => process.env.SITE_URL ?? "https://example.com",
};
```

- [ ] **Step 6: Verify install + typecheck**

Run (from `jobs/`): `npx tsc --noEmit`
Expected: no errors (no source beyond `env.ts` yet).

- [ ] **Step 7: Commit**

```bash
git add jobs/package.json jobs/tsconfig.json jobs/vitest.config.ts jobs/.env.example jobs/.gitignore jobs/src/lib/env.ts jobs/package-lock.json
git commit -m "feat(jobs): scaffold email jobs package"
```

---

## Task 5: Catalog snapshot reader for jobs

**Files:**
- Create: `jobs/src/lib/catalog.ts`
- Test: `jobs/src/lib/catalog.test.ts`

The jobs read the committed snapshot directly from the repo path and expose a small typed shape (camelCase) plus a `daysUntil` helper local to jobs (kept independent from the web package).

- [ ] **Step 1: Write the failing test**

```ts
// jobs/src/lib/catalog.test.ts
import { describe, expect, it } from "vitest";
import { parseCatalog, daysUntil, type JobExhibition } from "./catalog";

const RAW = {
  generated_at: "2026-05-30T00:00:00Z",
  exhibitions: [{
    id: "e1", title: "T", medium: "photo", exhibition_type: "solo",
    genre_tags: ["doc"], fee_type: "free", start_date: "2026-05-01", end_date: "2026-06-02",
    status: "ongoing", poster_image_url: "p", source_url: "s",
    venue: { id: "v", name: "한미", region: "서울", district: "삼청", lat: 37.5, lng: 126.9 },
    artists: [{ id: "a", name: "김작가" }],
  }],
  venues: [], artists: [],
};

describe("jobs catalog", () => {
  it("parses to typed exhibitions", () => {
    const cat = parseCatalog(RAW);
    const e: JobExhibition = cat.exhibitions[0];
    expect(e.id).toBe("e1");
    expect(e.region).toBe("서울");
    expect(e.artistNames).toEqual(["김작가"]);
    expect(e.genreTags).toEqual(["doc"]);
  });

  it("daysUntil counts whole days from a fixed today", () => {
    const today = new Date("2026-05-30T00:00:00+09:00");
    expect(daysUntil("2026-06-02", today)).toBe(3);
    expect(daysUntil("2026-05-31", today)).toBe(1);
    expect(daysUntil(null, today)).toBeNull();
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run (from `jobs/`): `npm run test -- catalog`
Expected: FAIL — cannot find `./catalog`.

- [ ] **Step 3: Write the implementation**

```ts
// jobs/src/lib/catalog.ts
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { dirname, resolve } from "node:path";

export interface JobExhibition {
  id: string; title: string;
  medium: string | null; exhibitionType: string | null;
  genreTags: string[]; feeType: string | null;
  startDate: string | null; endDate: string | null; status: string;
  posterImageUrl: string | null; sourceUrl: string | null;
  venueName: string | null; region: string | null; artistNames: string[];
}
export interface JobCatalog { generatedAt: string; exhibitions: JobExhibition[]; }

/* eslint-disable @typescript-eslint/no-explicit-any */
export function parseCatalog(raw: any): JobCatalog {
  return {
    generatedAt: raw.generated_at,
    exhibitions: (raw.exhibitions ?? []).map((e: any): JobExhibition => ({
      id: e.id, title: e.title,
      medium: e.medium ?? null, exhibitionType: e.exhibition_type ?? null,
      genreTags: e.genre_tags ?? [], feeType: e.fee_type ?? null,
      startDate: e.start_date ?? null, endDate: e.end_date ?? null, status: e.status ?? "unknown",
      posterImageUrl: e.poster_image_url ?? null, sourceUrl: e.source_url ?? null,
      venueName: e.venue?.name ?? null, region: e.venue?.region ?? null,
      artistNames: (e.artists ?? []).map((a: any) => a.name),
    })),
  };
}

export function loadCatalog(): JobCatalog {
  const here = dirname(fileURLToPath(import.meta.url));
  const path = resolve(here, "../../../web/public/data/exhibitions.json");
  return parseCatalog(JSON.parse(readFileSync(path, "utf8")));
}

const MS_PER_DAY = 86_400_000;
function atMidnight(d: Date): number {
  return Math.floor(new Date(d.getFullYear(), d.getMonth(), d.getDate()).getTime() / MS_PER_DAY);
}
export function daysUntil(endDate: string | null, today: Date = new Date()): number | null {
  if (!endDate) return null;
  return atMidnight(new Date(endDate + "T00:00:00")) - atMidnight(today);
}
```

- [ ] **Step 4: Run test to verify it passes**

Run (from `jobs/`): `npm run test -- catalog`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add jobs/src/lib/catalog.ts jobs/src/lib/catalog.test.ts
git commit -m "feat(jobs): catalog snapshot reader + daysUntil"
```

---

## Task 6: Pure matching logic

**Files:**
- Create: `jobs/src/lib/match.ts`
- Test: `jobs/src/lib/match.test.ts`

Two pure functions: `closingSoonForReminder` (exhibitions ending in exactly the reminder offsets, default {3,1}) and `matchCustom` (exhibitions matching a user's custom filters; empty filter arrays mean "no constraint on that dimension"; at least one filter must be set or it returns []).

- [ ] **Step 1: Write the failing test**

```ts
// jobs/src/lib/match.test.ts
import { describe, expect, it } from "vitest";
import { closingSoonForReminder, matchCustom } from "./match";
import type { JobExhibition } from "./catalog";

function ex(p: Partial<JobExhibition>): JobExhibition {
  return {
    id: "x", title: "T", medium: "photo", exhibitionType: "solo", genreTags: [],
    feeType: "free", startDate: "2026-05-01", endDate: "2026-06-30", status: "ongoing",
    posterImageUrl: null, sourceUrl: null, venueName: "V", region: "서울", artistNames: [], ...p,
  };
}
const TODAY = new Date("2026-05-30T00:00:00+09:00");

describe("closingSoonForReminder", () => {
  it("returns exhibitions ending in exactly 3 or 1 days", () => {
    const list = [
      ex({ id: "d3", endDate: "2026-06-02" }), // D-3
      ex({ id: "d1", endDate: "2026-05-31" }), // D-1
      ex({ id: "d2", endDate: "2026-06-01" }), // D-2 (excluded)
      ex({ id: "d0", endDate: "2026-05-30" }), // D-day (excluded)
    ];
    const out = closingSoonForReminder(list, TODAY);
    expect(out.map((e) => e.id).sort()).toEqual(["d1", "d3"]);
  });
});

describe("matchCustom", () => {
  it("matches by region OR medium across set dimensions (AND across dimensions)", () => {
    const list = [
      ex({ id: "a", region: "서울", medium: "photo" }),
      ex({ id: "b", region: "부산", medium: "photo" }),
      ex({ id: "c", region: "서울", medium: "video" }),
    ];
    // region in [서울] AND medium in [photo]
    expect(matchCustom(list, { regions: ["서울"], mediums: ["photo"] }).map((e) => e.id)).toEqual(["a"]);
    // only region constraint
    expect(matchCustom(list, { regions: ["서울"] }).map((e) => e.id)).toEqual(["a", "c"]);
  });
  it("returns [] when no filters are set", () => {
    expect(matchCustom([ex({})], {})).toEqual([]);
    expect(matchCustom([ex({})], { regions: [], mediums: [] })).toEqual([]);
  });
  it("matches by artist and genre", () => {
    const list = [
      ex({ id: "a", artistNames: ["김작가"] }),
      ex({ id: "b", genreTags: ["다큐"] }),
      ex({ id: "c", artistNames: ["다른작가"] }),
    ];
    expect(matchCustom(list, { artists: ["김작가"] }).map((e) => e.id)).toEqual(["a"]);
    expect(matchCustom(list, { genres: ["다큐"] }).map((e) => e.id)).toEqual(["b"]);
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run (from `jobs/`): `npm run test -- match`
Expected: FAIL — cannot find `./match`.

- [ ] **Step 3: Write the implementation**

```ts
// jobs/src/lib/match.ts
import { daysUntil, type JobExhibition } from "./catalog";

export interface CustomFilters {
  artists?: string[];
  regions?: string[];
  genres?: string[];
  mediums?: string[];
}

export function closingSoonForReminder(
  list: JobExhibition[],
  today: Date = new Date(),
  offsets: number[] = [3, 1],
): JobExhibition[] {
  const set = new Set(offsets);
  return list.filter((e) => {
    if (e.status !== "ongoing") return false;
    const d = daysUntil(e.endDate, today);
    return d != null && set.has(d);
  });
}

export function matchCustom(list: JobExhibition[], f: CustomFilters): JobExhibition[] {
  const dims: { values: string[] | undefined; pick: (e: JobExhibition) => string[] }[] = [
    { values: f.regions, pick: (e) => (e.region ? [e.region] : []) },
    { values: f.mediums, pick: (e) => (e.medium ? [e.medium] : []) },
    { values: f.artists, pick: (e) => e.artistNames },
    { values: f.genres, pick: (e) => e.genreTags },
  ];
  const active = dims.filter((d) => d.values && d.values.length > 0);
  if (active.length === 0) return [];
  return list.filter((e) =>
    active.every((d) => d.pick(e).some((v) => d.values!.includes(v))),
  );
}
```

- [ ] **Step 4: Run test to verify it passes**

Run (from `jobs/`): `npm run test -- match`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add jobs/src/lib/match.ts jobs/src/lib/match.test.ts
git commit -m "feat(jobs): pure closing-soon + custom-match logic"
```

---

## Task 7: Email-log dedupe layer

**Files:**
- Create: `jobs/src/lib/emailLog.ts`
- Test: `jobs/src/lib/emailLog.test.ts`

- [ ] **Step 1: Write the failing test**

```ts
// jobs/src/lib/emailLog.test.ts
import { describe, expect, it, vi } from "vitest";
import { loadSentRefs, recordSent } from "./emailLog";

function fakeClient(rows: { ref: string }[] = []) {
  const eq2 = vi.fn().mockResolvedValue({ data: rows, error: null });
  const eq1 = vi.fn(() => ({ eq: eq2 }));
  const select = vi.fn(() => ({ eq: eq1 }));
  const insert = vi.fn().mockResolvedValue({ error: null });
  const from = vi.fn(() => ({ select, insert }));
  return { client: { from } as any, from, select, eq1, eq2, insert };
}

describe("emailLog", () => {
  it("loadSentRefs returns a Set of refs for (user, type)", async () => {
    const f = fakeClient([{ ref: "r1" }, { ref: "r2" }]);
    const refs = await loadSentRefs(f.client, "u1", "closing_soon");
    expect(f.from).toHaveBeenCalledWith("email_log");
    expect(f.eq1).toHaveBeenCalledWith("user_id", "u1");
    expect(f.eq2).toHaveBeenCalledWith("type", "closing_soon");
    expect(refs).toEqual(new Set(["r1", "r2"]));
  });

  it("recordSent inserts one row per ref", async () => {
    const f = fakeClient();
    await recordSent(f.client, "u1", "custom", ["a", "b"]);
    expect(f.insert).toHaveBeenCalledWith([
      { user_id: "u1", type: "custom", ref: "a" },
      { user_id: "u1", type: "custom", ref: "b" },
    ]);
  });

  it("recordSent with no refs does nothing", async () => {
    const f = fakeClient();
    await recordSent(f.client, "u1", "custom", []);
    expect(f.insert).not.toHaveBeenCalled();
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run (from `jobs/`): `npm run test -- emailLog`
Expected: FAIL — cannot find `./emailLog`.

- [ ] **Step 3: Write the implementation**

```ts
// jobs/src/lib/emailLog.ts
import type { SupabaseClient } from "@supabase/supabase-js";

export async function loadSentRefs(
  client: SupabaseClient, userId: string, type: string,
): Promise<Set<string>> {
  const { data, error } = await client
    .from("email_log").select("ref").eq("user_id", userId).eq("type", type);
  if (error) throw error;
  return new Set((data ?? []).map((r: { ref: string }) => r.ref));
}

export async function recordSent(
  client: SupabaseClient, userId: string, type: string, refs: string[],
): Promise<void> {
  if (refs.length === 0) return;
  const { error } = await client
    .from("email_log").insert(refs.map((ref) => ({ user_id: userId, type, ref })));
  if (error) throw error;
}
```

- [ ] **Step 4: Run test to verify it passes**

Run (from `jobs/`): `npm run test -- emailLog`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add jobs/src/lib/emailLog.ts jobs/src/lib/emailLog.test.ts
git commit -m "feat(jobs): email-log dedupe layer"
```

---

## Task 8: Resend client + email templates

**Files:**
- Create: `jobs/src/lib/resendClient.ts`, `jobs/src/lib/render.ts`
- Test: `jobs/src/lib/render.test.ts`

- [ ] **Step 1: Write the failing test for the renderer**

```ts
// jobs/src/lib/render.test.ts
import { describe, expect, it } from "vitest";
import { renderDigest, renderClosingSoon } from "./render";
import type { JobExhibition } from "./catalog";

function ex(id: string, title: string): JobExhibition {
  return {
    id, title, medium: "photo", exhibitionType: "solo", genreTags: [], feeType: "free",
    startDate: "2026-05-01", endDate: "2026-06-02", status: "ongoing",
    posterImageUrl: "https://x/p.jpg", sourceUrl: "https://s/1", venueName: "한미", region: "서울",
    artistNames: ["김작가"],
  };
}

describe("render", () => {
  it("renderDigest includes each exhibition title and a link to the site detail", () => {
    const html = renderDigest([ex("e1", "빛"), ex("e2", "그림자")], "https://frame.example");
    expect(html).toContain("빛");
    expect(html).toContain("그림자");
    expect(html).toContain("https://frame.example/exhibitions/e1");
  });
  it("renderClosingSoon shows the D-day per item", () => {
    const html = renderClosingSoon([{ e: ex("e1", "빛"), dday: 3 }], "https://frame.example");
    expect(html).toContain("D-3");
    expect(html).toContain("빛");
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run (from `jobs/`): `npm run test -- render`
Expected: FAIL — cannot find `./render`.

- [ ] **Step 3: Write `render.ts`**

```ts
// jobs/src/lib/render.ts
import type { JobExhibition } from "./catalog";

function esc(s: string): string {
  return s.replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]!));
}

function card(e: JobExhibition, siteUrl: string, badge?: string): string {
  const url = `${siteUrl}/exhibitions/${encodeURIComponent(e.id)}`;
  const sub = [e.venueName, e.region].filter(Boolean).map((s) => esc(s!)).join(" · ");
  return `
    <tr><td style="padding:12px 0;border-bottom:1px solid #222;">
      <a href="${url}" style="color:#fff;text-decoration:none;font-weight:700;font-size:16px;">
        ${badge ? `<span style="background:#fff;color:#000;border-radius:999px;padding:2px 8px;font-size:11px;margin-right:8px;">${esc(badge)}</span>` : ""}${esc(e.title)}
      </a>
      <div style="color:#9a9a9a;font-size:13px;margin-top:4px;">${sub}</div>
    </td></tr>`;
}

function shell(title: string, body: string): string {
  return `<!doctype html><html><body style="margin:0;background:#000;color:#fff;font-family:-apple-system,BlinkMacSystemFont,Helvetica,Arial,sans-serif;">
    <table width="100%" cellpadding="0" cellspacing="0" style="max-width:560px;margin:0 auto;padding:28px;">
      <tr><td style="font-weight:800;font-size:22px;letter-spacing:-0.03em;padding-bottom:8px;">FRAME</td></tr>
      <tr><td style="color:#9a9a9a;font-size:14px;padding-bottom:16px;">${esc(title)}</td></tr>
      ${body}
    </table></body></html>`;
}

export function renderDigest(items: JobExhibition[], siteUrl: string): string {
  const rows = items.map((e) => card(e, siteUrl)).join("");
  return shell("이번 주의 전시", `<tr><td><table width="100%">${rows}</table></td></tr>`);
}

export function renderClosingSoon(items: { e: JobExhibition; dday: number }[], siteUrl: string): string {
  const rows = items.map(({ e, dday }) => card(e, siteUrl, `D-${dday}`)).join("");
  return shell("스크랩한 전시가 곧 끝나요", `<tr><td><table width="100%">${rows}</table></td></tr>`);
}

export function renderCustom(items: JobExhibition[], siteUrl: string): string {
  const rows = items.map((e) => card(e, siteUrl, "NEW")).join("");
  return shell("관심 조건에 맞는 새 전시", `<tr><td><table width="100%">${rows}</table></td></tr>`);
}
```

- [ ] **Step 4: Write `resendClient.ts` (thin, injectable)**

```ts
// jobs/src/lib/resendClient.ts
import { Resend } from "resend";
import { env } from "./env";

export interface Mailer { send(to: string, subject: string, html: string): Promise<void>; }

export function makeResendMailer(): Mailer {
  const resend = new Resend(env.resendApiKey());
  const from = env.emailFrom();
  return {
    async send(to, subject, html) {
      const { error } = await resend.emails.send({ from, to, subject, html });
      if (error) throw new Error(`Resend failed for ${to}: ${error.message}`);
    },
  };
}
```

- [ ] **Step 5: Run test to verify it passes**

Run (from `jobs/`): `npm run test -- render`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add jobs/src/lib/render.ts jobs/src/lib/render.test.ts jobs/src/lib/resendClient.ts
git commit -m "feat(jobs): resend client + email templates"
```

---

## Task 9: Service-role Supabase client + recipient queries

**Files:**
- Create: `jobs/src/lib/supabaseAdmin.ts`

(No unit test — it is a thin factory and query helpers over the real client; exercised by the job entries in Tasks 10–12 and verified with a dry run.)

- [ ] **Step 1: Write `supabaseAdmin.ts`**

```ts
// jobs/src/lib/supabaseAdmin.ts
import { createClient, type SupabaseClient } from "@supabase/supabase-js";
import { env } from "./env";

export function makeAdminClient(): SupabaseClient {
  return createClient(env.supabaseUrl(), env.supabaseServiceKey(), {
    auth: { persistSession: false, autoRefreshToken: false },
  });
}

export interface Subscriber { userId: string; email: string; filters: Record<string, string[]>; }

/** Enabled subscribers of a given type, joined to their email from profiles. */
export async function subscribersOf(
  client: SupabaseClient, type: "weekly_digest" | "closing_soon" | "custom",
): Promise<Subscriber[]> {
  const { data, error } = await client
    .from("subscriptions")
    .select("user_id, filters, profiles!inner(email)")
    .eq("type", type)
    .eq("enabled", true);
  if (error) throw error;
  return (data ?? [])
    .map((r: any) => ({
      userId: r.user_id,
      email: r.profiles?.email ?? "",
      filters: r.filters ?? {},
    }))
    .filter((s: Subscriber) => s.email);
}

/** Exhibition ids a user has scrapped. */
export async function bookmarksOf(client: SupabaseClient, userId: string): Promise<string[]> {
  const { data, error } = await client.from("bookmarks").select("exhibition_id").eq("user_id", userId);
  if (error) throw error;
  return (data ?? []).map((r: { exhibition_id: string }) => r.exhibition_id);
}
```
(The `profiles!inner(email)` join requires the FK from `subscriptions.user_id`→`auth.users` and `profiles.id`→`auth.users`; PostgREST resolves the relationship through `auth.users`. If the embed errors at runtime, fall back to two queries: fetch subscriptions, then `profiles` by `in('id', userIds)`, and merge in JS. Confirm during the Task 10 dry run.)

- [ ] **Step 2: Typecheck**

Run (from `jobs/`): `npx tsc --noEmit`
Expected: no errors.

- [ ] **Step 3: Commit**

```bash
git add jobs/src/lib/supabaseAdmin.ts
git commit -m "feat(jobs): service-role client + recipient queries"
```

---

## Task 10: Weekly digest job

**Files:**
- Create: `jobs/src/weekly-digest.ts`

- [ ] **Step 1: Write the job entry**

Sends every `weekly_digest` subscriber the ongoing/upcoming exhibitions (cap ~12, ordered closing-soon first). Dedupe ref = ISO-week (`YYYY-Www`), so re-running the same week is a no-op.

```ts
// jobs/src/weekly-digest.ts
import { loadCatalog, daysUntil } from "./lib/catalog";
import { makeAdminClient, subscribersOf } from "./lib/supabaseAdmin";
import { loadSentRefs, recordSent } from "./lib/emailLog";
import { makeResendMailer, type Mailer } from "./lib/resendClient";
import { renderDigest } from "./lib/render";
import { env } from "./lib/env";

function isoWeek(d: Date): string {
  const date = new Date(Date.UTC(d.getFullYear(), d.getMonth(), d.getDate()));
  const day = date.getUTCDay() || 7;
  date.setUTCDate(date.getUTCDate() + 4 - day);
  const yearStart = new Date(Date.UTC(date.getUTCFullYear(), 0, 1));
  const week = Math.ceil(((date.getTime() - yearStart.getTime()) / 86400000 + 1) / 7);
  return `${date.getUTCFullYear()}-W${String(week).padStart(2, "0")}`;
}

export async function runWeeklyDigest(deps?: { mailer?: Mailer; today?: Date }): Promise<number> {
  const today = deps?.today ?? new Date();
  const mailer = deps?.mailer ?? makeResendMailer();
  const client = makeAdminClient();
  const ref = isoWeek(today);

  const catalog = loadCatalog();
  const featured = catalog.exhibitions
    .filter((e) => e.status === "ongoing" || e.status === "upcoming")
    .sort((a, b) => {
      const da = daysUntil(a.endDate, today) ?? 9999;
      const db = daysUntil(b.endDate, today) ?? 9999;
      return da - db;
    })
    .slice(0, 12);
  if (featured.length === 0) return 0;

  let sent = 0;
  for (const sub of await subscribersOf(client, "weekly_digest")) {
    const already = await loadSentRefs(client, sub.userId, "weekly_digest");
    if (already.has(ref)) continue;
    await mailer.send(sub.email, "FRAME 주간 다이제스트", renderDigest(featured, env.siteUrl()));
    await recordSent(client, sub.userId, "weekly_digest", [ref]);
    sent++;
  }
  console.log(`weekly-digest: sent ${sent}`);
  return sent;
}

// Run when invoked directly.
if (import.meta.url === `file://${process.argv[1]}`) {
  runWeeklyDigest().catch((e) => { console.error(e); process.exit(1); });
}
```

- [ ] **Step 2: Dry run locally (optional, requires env + a test subscriber)**

With `jobs/.env` filled and a `weekly_digest` subscription enabled for your own account, run (from `jobs/`): `npm run weekly-digest`. Expect a log line and one email to your inbox. Re-run immediately → `sent 0` (deduped by week). If the `subscribersOf` embed errors, apply the two-query fallback noted in Task 9.

- [ ] **Step 3: Commit**

```bash
git add jobs/src/weekly-digest.ts
git commit -m "feat(jobs): weekly digest email job"
```

---

## Task 11: Closing-soon job

**Files:**
- Create: `jobs/src/closing-soon.ts`

- [ ] **Step 1: Write the job entry**

For each `closing_soon` subscriber, intersect their bookmarks with catalog exhibitions ending in {3,1} days; email the list. Dedupe ref = `exhibitionId:dday` so D-3 and D-1 each send once.

```ts
// jobs/src/closing-soon.ts
import { loadCatalog, daysUntil } from "./lib/catalog";
import { makeAdminClient, subscribersOf, bookmarksOf } from "./lib/supabaseAdmin";
import { loadSentRefs, recordSent } from "./lib/emailLog";
import { makeResendMailer, type Mailer } from "./lib/resendClient";
import { renderClosingSoon } from "./lib/render";
import { env } from "./lib/env";

export async function runClosingSoon(deps?: { mailer?: Mailer; today?: Date }): Promise<number> {
  const today = deps?.today ?? new Date();
  const mailer = deps?.mailer ?? makeResendMailer();
  const client = makeAdminClient();
  const catalog = loadCatalog();
  const byId = new Map(catalog.exhibitions.map((e) => [e.id, e]));

  let sent = 0;
  for (const sub of await subscribersOf(client, "closing_soon")) {
    const ids = await bookmarksOf(client, sub.userId);
    const due: { e: typeof catalog.exhibitions[number]; dday: number }[] = [];
    for (const id of ids) {
      const e = byId.get(id);
      if (!e || e.status !== "ongoing") continue;
      const d = daysUntil(e.endDate, today);
      if (d === 3 || d === 1) due.push({ e, dday: d });
    }
    if (due.length === 0) continue;

    const already = await loadSentRefs(client, sub.userId, "closing_soon");
    const fresh = due.filter(({ e, dday }) => !already.has(`${e.id}:${dday}`));
    if (fresh.length === 0) continue;

    await mailer.send(sub.email, "곧 종료되는 스크랩 전시", renderClosingSoon(fresh, env.siteUrl()));
    await recordSent(client, sub.userId, "closing_soon", fresh.map(({ e, dday }) => `${e.id}:${dday}`));
    sent++;
  }
  console.log(`closing-soon: sent ${sent}`);
  return sent;
}

if (import.meta.url === `file://${process.argv[1]}`) {
  runClosingSoon().catch((e) => { console.error(e); process.exit(1); });
}
```

- [ ] **Step 2: Commit**

```bash
git add jobs/src/closing-soon.ts
git commit -m "feat(jobs): closing-soon reminder job"
```

---

## Task 12: Custom-alerts job

**Files:**
- Create: `jobs/src/custom-alerts.ts`

- [ ] **Step 1: Write the job entry**

For each `custom` subscriber, match catalog exhibitions to their filters, skip ids already in the log (the implicit "new" definition), email the rest, and log by `exhibitionId`.

```ts
// jobs/src/custom-alerts.ts
import { loadCatalog } from "./lib/catalog";
import { makeAdminClient, subscribersOf } from "./lib/supabaseAdmin";
import { loadSentRefs, recordSent } from "./lib/emailLog";
import { makeResendMailer, type Mailer } from "./lib/resendClient";
import { matchCustom, type CustomFilters } from "./lib/match";
import { renderCustom } from "./lib/render";
import { env } from "./lib/env";

export async function runCustomAlerts(deps?: { mailer?: Mailer }): Promise<number> {
  const mailer = deps?.mailer ?? makeResendMailer();
  const client = makeAdminClient();
  const catalog = loadCatalog();

  let sent = 0;
  for (const sub of await subscribersOf(client, "custom")) {
    const matched = matchCustom(catalog.exhibitions, sub.filters as CustomFilters);
    if (matched.length === 0) continue;

    const already = await loadSentRefs(client, sub.userId, "custom");
    const fresh = matched.filter((e) => !already.has(e.id));
    if (fresh.length === 0) continue;

    await mailer.send(sub.email, "관심 조건에 맞는 새 전시", renderCustom(fresh.slice(0, 12), env.siteUrl()));
    await recordSent(client, sub.userId, "custom", fresh.map((e) => e.id));
    sent++;
  }
  console.log(`custom-alerts: sent ${sent}`);
  return sent;
}

if (import.meta.url === `file://${process.argv[1]}`) {
  runCustomAlerts().catch((e) => { console.error(e); process.exit(1); });
}
```

- [ ] **Step 2: Full jobs test + typecheck**

Run (from `jobs/`): `npm run test` → all green. `npx tsc --noEmit` → no errors.

- [ ] **Step 3: Commit**

```bash
git add jobs/src/custom-alerts.ts
git commit -m "feat(jobs): custom-filter alert job"
```

---

## Task 13: GitHub Actions cron for email jobs

**Files:**
- Create: `.github/workflows/emails-weekly.yml`, `.github/workflows/emails-daily.yml`

- [ ] **Step 1: Add the weekly workflow**

```yaml
# .github/workflows/emails-weekly.yml
name: emails-weekly
on:
  schedule:
    - cron: '0 0 * * 1'   # Mon 09:00 KST = 00:00 UTC
  workflow_dispatch:
concurrency:
  group: emails-weekly
  cancel-in-progress: false
jobs:
  weekly:
    runs-on: ubuntu-latest
    timeout-minutes: 10
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-node@v4
        with:
          node-version: '20'
      - run: npm ci
        working-directory: jobs
      - run: npm run weekly-digest
        working-directory: jobs
        env:
          SUPABASE_URL: ${{ secrets.SUPABASE_URL }}
          SUPABASE_SERVICE_ROLE_KEY: ${{ secrets.SUPABASE_SERVICE_ROLE_KEY }}
          RESEND_API_KEY: ${{ secrets.RESEND_API_KEY }}
          EMAIL_FROM: ${{ secrets.EMAIL_FROM }}
          SITE_URL: ${{ secrets.SITE_URL }}
```

- [ ] **Step 2: Add the daily workflow (closing-soon + custom)**

```yaml
# .github/workflows/emails-daily.yml
name: emails-daily
on:
  schedule:
    - cron: '0 1 * * *'   # daily 10:00 KST = 01:00 UTC (after the 18:00 UTC crawl refresh)
  workflow_dispatch:
concurrency:
  group: emails-daily
  cancel-in-progress: false
jobs:
  daily:
    runs-on: ubuntu-latest
    timeout-minutes: 10
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-node@v4
        with:
          node-version: '20'
      - run: npm ci
        working-directory: jobs
      - run: npm run closing-soon
        working-directory: jobs
        env:
          SUPABASE_URL: ${{ secrets.SUPABASE_URL }}
          SUPABASE_SERVICE_ROLE_KEY: ${{ secrets.SUPABASE_SERVICE_ROLE_KEY }}
          RESEND_API_KEY: ${{ secrets.RESEND_API_KEY }}
          EMAIL_FROM: ${{ secrets.EMAIL_FROM }}
          SITE_URL: ${{ secrets.SITE_URL }}
      - run: npm run custom-alerts
        working-directory: jobs
        env:
          SUPABASE_URL: ${{ secrets.SUPABASE_URL }}
          SUPABASE_SERVICE_ROLE_KEY: ${{ secrets.SUPABASE_SERVICE_ROLE_KEY }}
          RESEND_API_KEY: ${{ secrets.RESEND_API_KEY }}
          EMAIL_FROM: ${{ secrets.EMAIL_FROM }}
          SITE_URL: ${{ secrets.SITE_URL }}
```

- [ ] **Step 3: Note the required GitHub secrets**

In the repo Settings → Secrets and variables → Actions, add: `SUPABASE_URL`, `SUPABASE_SERVICE_ROLE_KEY`, `RESEND_API_KEY`, `EMAIL_FROM`, `SITE_URL`. (Document this in the commit message; do not hardcode any value.)

- [ ] **Step 4: Validate YAML**

Run (repo root): `python -c "import yaml; [yaml.safe_load(open(f)) for f in ['.github/workflows/emails-weekly.yml','.github/workflows/emails-daily.yml']]"`
Expected: no parse errors.

- [ ] **Step 5: Commit**

```bash
git add .github/workflows/emails-weekly.yml .github/workflows/emails-daily.yml
git commit -m "ci: schedule weekly + daily email jobs"
```

---

## Self-Review (completed during planning)

**Spec coverage:**
- §7 DB model: `subscriptions` (type/enabled/filters jsonb) + `email_log` (dedupe) with RLS → Task 1. `custom filters: { artists, regions, genres, mediums }` → `CustomFilters` (Tasks 2, 6).
- §8 email system: weekly digest (Task 10), closing-soon for scraps at D-3/D-1 (Task 11), custom match for new exhibitions (Task 12), Resend (Task 8), GitHub Actions cron (Task 13), `email_log` dedupe after send (Task 7, used by all three jobs).
- Settings UI for the three subscription types → Task 3 (mounted in 마이 from Plan 3).

**Placeholder scan:** No TBD/TODO. The `subscribersOf` PostgREST embed has an explicit, documented two-query fallback rather than a vague "handle errors." Secrets are referenced via `${{ secrets.* }}`, never inlined.

**Type consistency:**
- `SubType` = `"weekly_digest" | "closing_soon" | "custom"` matches the SQL `check` constraint (Task 1) and the UI rows (Task 3) and `subscribersOf` arg (Task 9).
- `CustomFilters` shape (`artists/regions/genres/mediums`, all optional `string[]`) is identical in the web layer (Task 2), the jobs match logic (Task 6), and the `filters` jsonb default (Task 1).
- `email_log(user_id, type, ref)` columns match the dedupe layer's queries (Task 7) and every job's `recordSent`/`loadSentRefs` usage (Tasks 10–12).
- Jobs read the catalog via `loadCatalog()` → `JobExhibition` (Task 5); `closingSoonForReminder`/`matchCustom` consume `JobExhibition` consistently (Task 6, 11, 12).
- `Mailer` interface is injectable in every job (Tasks 10–12) so tests can pass a fake; the real `makeResendMailer` (Task 8) is the default.

**Idempotency:** every job is safe to re-run — weekly by ISO-week ref, closing-soon by `id:dday`, custom by `id`. Daily workflow runs after the 18:00 UTC crawl refresh so the snapshot is current.

**Security:** service role key is server-only (GitHub secrets + gitignored `jobs/.env`), never in `NEXT_PUBLIC_*`. RLS still enabled on both tables; the web app uses the anon key and can only read/write the caller's own rows.
