# Auth & Scrap (Supabase) — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add Google login and persistent scrap (bookmark) to the discovery app from Plan 2, backed by Supabase (Postgres + Auth) with Row Level Security so each user only touches their own data.

**Architecture:** The catalog stays a static JSON read on the client (Plan 1/2 unchanged). A second "user plane" is added: a Supabase project provides Google OAuth and two tables (`profiles`, `bookmarks`). Because the web app is statically exported (`output: "export"`), all auth is client-side — the Supabase JS client uses the PKCE flow and parses the OAuth redirect in the browser (`detectSessionInUrl`), so **no server route handler is required**. A React context exposes the session; a small `bookmarks` data layer (pure functions over a Supabase client, unit-tested with a fake) powers the ScrapButton, the 스크랩 page, and the 마이 page.

**Tech Stack:** `@supabase/supabase-js` v2, Supabase Auth (Google OAuth, PKCE), Postgres + RLS, React context, Vitest (fake Supabase client for the data layer).

---

## Background for the implementer

- This plan builds **directly on Plan 2** (`docs/superpowers/plans/2026-05-30-web-app-discovery.md`). The web app lives in `web/`. All commands run from `web/` unless noted.
- Re-read spec `docs/superpowers/specs/2026-05-30-exhibition-site-design.md` §5.2 (user plane), §7 (Supabase DB model), and the design tone in §3 before starting.
- **Existing contracts from Plan 2 you must reuse, not redefine:**
  - `Exhibition` (camelCase) in `web/src/lib/catalog.ts` — `Exhibition.id` (string) is the bookmark reference.
  - `ScrapButton` in `web/src/components/ScrapButton.tsx` is currently **visual-only** with signature `{ active?: boolean }`. This plan rewrites it to be functional. Every existing usage (`ExhibitionCard`, `SwipeDeck`, detail page) must keep working.
  - `loadCatalogSync()` in `web/src/lib/catalogClient.ts` returns the in-memory `Catalog`.
  - `Nav.tsx` already renders a desktop "로그인" button and `/scrap` + `/me` links (they 404 today). This plan makes them real.
- **Design tokens (unchanged):** bg `#000`, panel `#0c0c0c`/`#141414`, line `rgba(255,255,255,.13)`, text `#fff`/`#9a9a9a`/`#5e5e5e`. Accent = inversion (white bg + black text). Icons via `lucide-react`, never emoji.
- **Static-export constraint:** no Next.js Route Handlers or Server Actions. Auth and all Supabase calls happen in client components. The OAuth `redirectTo` is the site origin; Supabase JS exchanges the `?code=` automatically on load.
- **Secrets:** the anon key is public by design (RLS protects data). It goes in `NEXT_PUBLIC_*` env vars committed only as `.env.example`; real values live in `.env.local` (gitignored) and Vercel env.

## File Structure

```
web/
  .env.example                 # documents NEXT_PUBLIC_SUPABASE_URL / _ANON_KEY
  src/
    lib/
      supabase.ts              # browser Supabase client (singleton)
      bookmarks.ts             # pure data layer: list/add/remove (takes a client)
    components/
      AuthProvider.tsx         # session context + useAuth() + useBookmarks()
      ScrapButton.tsx          # REWRITTEN: functional, persists via bookmarks layer
      LoginButton.tsx          # desktop login / avatar+logout
    app/
      scrap/page.tsx           # 스크랩 — bookmarked exhibitions, closing-soon sort
      me/page.tsx              # 마이 — login state, sign out
supabase/
  migrations/0001_user_plane.sql   # profiles + bookmarks + RLS (run in Supabase SQL editor)
```

---

## Task 1: Supabase client + env wiring

**Files:**
- Create: `web/src/lib/supabase.ts`, `web/.env.example`
- Modify: `web/.gitignore` (ensure `.env*.local` ignored — create-next-app usually adds this; verify), `web/package.json` (dep)

- [ ] **Step 1: Install the Supabase SDK**

Run (from `web/`):
```bash
npm i @supabase/supabase-js
```

- [ ] **Step 2: Create `web/.env.example`**

```
# Supabase (Project Settings → API). Anon key is public; RLS protects data.
NEXT_PUBLIC_SUPABASE_URL=https://YOUR-PROJECT.supabase.co
NEXT_PUBLIC_SUPABASE_ANON_KEY=YOUR-ANON-KEY
```

Then copy it to a real local file the implementer fills with their project values:
```bash
cp .env.example .env.local
```
Verify `.env.local` (and `.env*.local`) is gitignored:
```bash
grep -q ".env*.local" .gitignore || echo ".env*.local" >> .gitignore
```

- [ ] **Step 3: Create the browser client singleton**

```ts
// web/src/lib/supabase.ts
import { createClient, type SupabaseClient } from "@supabase/supabase-js";

let client: SupabaseClient | null = null;

export function getSupabase(): SupabaseClient {
  if (client) return client;
  const url = process.env.NEXT_PUBLIC_SUPABASE_URL;
  const anon = process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY;
  if (!url || !anon) {
    throw new Error("Missing NEXT_PUBLIC_SUPABASE_URL / NEXT_PUBLIC_SUPABASE_ANON_KEY");
  }
  client = createClient(url, anon, {
    auth: { flowType: "pkce", detectSessionInUrl: true, persistSession: true, autoRefreshToken: true },
  });
  return client;
}
```

- [ ] **Step 4: Verify it compiles**

Run (from `web/`): `npx tsc --noEmit`
Expected: no errors. (The client is not yet imported anywhere; this just type-checks the file.)

- [ ] **Step 5: Commit**

```bash
git add web/src/lib/supabase.ts web/.env.example web/.gitignore web/package.json web/package-lock.json
git commit -m "feat(web): supabase browser client + env scaffolding"
```

---

## Task 2: Database schema + RLS migration

**Files:**
- Create: `supabase/migrations/0001_user_plane.sql`

- [ ] **Step 1: Write the migration SQL**

```sql
-- supabase/migrations/0001_user_plane.sql
-- User plane for the FRAME discovery app: profiles + bookmarks, RLS-protected.

-- profiles: one row per auth user.
create table if not exists public.profiles (
  id uuid primary key references auth.users(id) on delete cascade,
  email text,
  created_at timestamptz not null default now()
);

-- bookmarks (scrap): a user's saved exhibitions. exhibition_id is the catalog id (string).
create table if not exists public.bookmarks (
  user_id uuid not null references auth.users(id) on delete cascade,
  exhibition_id text not null,
  created_at timestamptz not null default now(),
  primary key (user_id, exhibition_id)
);

create index if not exists bookmarks_user_idx on public.bookmarks (user_id, created_at desc);

-- Auto-create a profile row when a new auth user signs up.
create or replace function public.handle_new_user()
returns trigger
language plpgsql
security definer set search_path = public
as $$
begin
  insert into public.profiles (id, email)
  values (new.id, new.email)
  on conflict (id) do nothing;
  return new;
end;
$$;

drop trigger if exists on_auth_user_created on auth.users;
create trigger on_auth_user_created
  after insert on auth.users
  for each row execute function public.handle_new_user();

-- Row Level Security: each user only sees/edits their own rows.
alter table public.profiles enable row level security;
alter table public.bookmarks enable row level security;

drop policy if exists "profiles self read"  on public.profiles;
drop policy if exists "profiles self write" on public.profiles;
create policy "profiles self read"  on public.profiles
  for select using (auth.uid() = id);
create policy "profiles self write" on public.profiles
  for update using (auth.uid() = id) with check (auth.uid() = id);

drop policy if exists "bookmarks self all" on public.bookmarks;
create policy "bookmarks self all" on public.bookmarks
  for all using (auth.uid() = user_id) with check (auth.uid() = user_id);
```

- [ ] **Step 2: Apply the migration in Supabase**

Open the Supabase project → SQL Editor → paste the file contents → Run. Expected: success, two tables visible under Table Editor with RLS enabled (lock icon). Then enable **Google** under Authentication → Providers (set the Google OAuth client id/secret from Google Cloud Console; add the Supabase callback URL `https://YOUR-PROJECT.supabase.co/auth/v1/callback` to the Google client's authorized redirect URIs, and add the site URL + `http://localhost:3000` to Auth → URL Configuration → Redirect URLs).

- [ ] **Step 3: Commit**

```bash
git add supabase/migrations/0001_user_plane.sql
git commit -m "feat(db): user-plane schema (profiles, bookmarks) with RLS"
```

---

## Task 3: Bookmarks data layer (pure, fake-testable)

**Files:**
- Create: `web/src/lib/bookmarks.ts`
- Test: `web/src/lib/bookmarks.test.ts`

- [ ] **Step 1: Write the failing test (fake Supabase client)**

```ts
// web/src/lib/bookmarks.test.ts
import { describe, expect, it, vi } from "vitest";
import { addBookmark, listBookmarkIds, removeBookmark } from "@/lib/bookmarks";

// Minimal fake matching the calls our data layer makes.
function fakeClient(rows: { exhibition_id: string }[] = []) {
  const select = vi.fn().mockResolvedValue({ data: rows, error: null });
  const insert = vi.fn().mockResolvedValue({ error: null });
  const eq2 = vi.fn().mockResolvedValue({ error: null });
  const eq1 = vi.fn(() => ({ eq: eq2 }));
  const del = vi.fn(() => ({ eq: eq1 }));
  const from = vi.fn(() => ({ select, insert, delete: del }));
  return { client: { from } as any, from, select, insert, del, eq1, eq2 };
}

describe("bookmarks data layer", () => {
  it("listBookmarkIds returns a Set of exhibition ids", async () => {
    const f = fakeClient([{ exhibition_id: "e1" }, { exhibition_id: "e2" }]);
    const ids = await listBookmarkIds(f.client, "u1");
    expect(f.from).toHaveBeenCalledWith("bookmarks");
    expect(ids).toEqual(new Set(["e1", "e2"]));
  });

  it("addBookmark inserts user_id + exhibition_id", async () => {
    const f = fakeClient();
    await addBookmark(f.client, "u1", "e9");
    expect(f.insert).toHaveBeenCalledWith({ user_id: "u1", exhibition_id: "e9" });
  });

  it("removeBookmark deletes by user_id + exhibition_id", async () => {
    const f = fakeClient();
    await removeBookmark(f.client, "u1", "e9");
    expect(f.del).toHaveBeenCalled();
    expect(f.eq1).toHaveBeenCalledWith("user_id", "u1");
    expect(f.eq2).toHaveBeenCalledWith("exhibition_id", "e9");
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `npm run test -- bookmarks`
Expected: FAIL — cannot find `@/lib/bookmarks`.

- [ ] **Step 3: Write the implementation**

```ts
// web/src/lib/bookmarks.ts
import type { SupabaseClient } from "@supabase/supabase-js";

export async function listBookmarkIds(client: SupabaseClient, userId: string): Promise<Set<string>> {
  const { data, error } = await client.from("bookmarks").select("exhibition_id").eq("user_id", userId);
  if (error) throw error;
  return new Set((data ?? []).map((r: { exhibition_id: string }) => r.exhibition_id));
}

export async function addBookmark(client: SupabaseClient, userId: string, exhibitionId: string): Promise<void> {
  const { error } = await client.from("bookmarks").insert({ user_id: userId, exhibition_id: exhibitionId });
  if (error) throw error;
}

export async function removeBookmark(client: SupabaseClient, userId: string, exhibitionId: string): Promise<void> {
  const { error } = await client.from("bookmarks").delete().eq("user_id", userId).eq("exhibition_id", exhibitionId);
  if (error) throw error;
}
```

Note: in `listBookmarkIds` the test's fake resolves `select(...)` directly (no `.eq`), while production chains `.eq("user_id", ...)`. Make the fake's `select` return an object that is also awaitable. Adjust the fake so `select` returns `{ eq: () => Promise.resolve({ data: rows, error: null }) }`:

```ts
// Replace the fake's select line in the test with:
const eqSel = vi.fn().mockResolvedValue({ data: rows, error: null });
const select = vi.fn(() => ({ eq: eqSel }));
// ...and assert: expect(eqSel).toHaveBeenCalledWith("user_id", "u1");
```
(Apply this corrected fake before running; it keeps the production code chain `.select(...).eq(...)` honest.)

- [ ] **Step 4: Run test to verify it passes**

Run: `npm run test -- bookmarks`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add web/src/lib/bookmarks.ts web/src/lib/bookmarks.test.ts
git commit -m "feat(web): bookmarks data layer (list/add/remove)"
```

---

## Task 4: Auth + bookmarks context (`AuthProvider`)

**Files:**
- Create: `web/src/components/AuthProvider.tsx`
- Modify: `web/src/app/layout.tsx` (wrap children)
- Test: `web/src/components/AuthProvider.test.tsx`

- [ ] **Step 1: Write the failing test**

The provider exposes `useAuth()` (session/user/signIn/signOut) and `useBookmarks()` (a Set + toggle + isScrapped). Test the bookmark toggle reducer logic in isolation by rendering a tiny consumer with a mocked supabase + bookmarks layer.

```tsx
// web/src/components/AuthProvider.test.tsx
import { act, render, screen } from "@testing-library/react";
import { describe, expect, it, vi, beforeEach } from "vitest";

// Mock the supabase client and bookmarks layer so the provider has no network.
const authState = { user: { id: "u1", email: "a@b.c" } as any };
vi.mock("@/lib/supabase", () => ({
  getSupabase: () => ({
    auth: {
      getSession: vi.fn().mockResolvedValue({ data: { session: { user: authState.user } } }),
      onAuthStateChange: vi.fn(() => ({ data: { subscription: { unsubscribe: vi.fn() } } })),
      signInWithOAuth: vi.fn(),
      signOut: vi.fn(),
    },
  }),
}));
vi.mock("@/lib/bookmarks", () => ({
  listBookmarkIds: vi.fn().mockResolvedValue(new Set<string>(["e1"])),
  addBookmark: vi.fn().mockResolvedValue(undefined),
  removeBookmark: vi.fn().mockResolvedValue(undefined),
}));

import { AuthProvider, useAuth, useBookmarks } from "@/components/AuthProvider";

function Probe() {
  const { user } = useAuth();
  const { isScrapped, toggle } = useBookmarks();
  return (
    <div>
      <span data-testid="user">{user?.email ?? "none"}</span>
      <span data-testid="e1">{isScrapped("e1") ? "yes" : "no"}</span>
      <button onClick={() => toggle("e2")}>add-e2</button>
      <span data-testid="e2">{isScrapped("e2") ? "yes" : "no"}</span>
    </div>
  );
}

describe("AuthProvider", () => {
  beforeEach(() => vi.clearAllMocks());

  it("loads session + initial bookmarks and toggles optimistically", async () => {
    render(<AuthProvider><Probe /></AuthProvider>);
    // session + initial bookmarks resolve on mount
    expect(await screen.findByText("a@b.c")).toBeInTheDocument();
    expect(screen.getByTestId("e1")).toHaveTextContent("yes");
    expect(screen.getByTestId("e2")).toHaveTextContent("no");

    await act(async () => { screen.getByText("add-e2").click(); });
    expect(screen.getByTestId("e2")).toHaveTextContent("yes"); // optimistic add
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `npm run test -- AuthProvider`
Expected: FAIL — cannot find `@/components/AuthProvider`.

- [ ] **Step 3: Write the provider**

```tsx
// web/src/components/AuthProvider.tsx
"use client";
import { createContext, useCallback, useContext, useEffect, useMemo, useState } from "react";
import type { Session, User } from "@supabase/supabase-js";
import { getSupabase } from "@/lib/supabase";
import { addBookmark, listBookmarkIds, removeBookmark } from "@/lib/bookmarks";

interface AuthCtx {
  user: User | null;
  session: Session | null;
  loading: boolean;
  signIn: () => Promise<void>;
  signOut: () => Promise<void>;
}
interface BookmarksCtx {
  ids: Set<string>;
  isScrapped: (id: string) => boolean;
  toggle: (id: string) => Promise<void>;
}

const AuthContext = createContext<AuthCtx | null>(null);
const BookmarksContext = createContext<BookmarksCtx | null>(null);

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const supabase = getSupabase();
  const [session, setSession] = useState<Session | null>(null);
  const [loading, setLoading] = useState(true);
  const [ids, setIds] = useState<Set<string>>(new Set());

  const user = session?.user ?? null;

  // Load session + subscribe to changes.
  useEffect(() => {
    let active = true;
    supabase.auth.getSession().then(({ data }) => {
      if (active) { setSession(data.session ?? null); setLoading(false); }
    });
    const { data: sub } = supabase.auth.onAuthStateChange((_e, s) => setSession(s));
    return () => { active = false; sub.subscription.unsubscribe(); };
  }, [supabase]);

  // Load bookmarks whenever the user changes.
  useEffect(() => {
    if (!user) { setIds(new Set()); return; }
    let active = true;
    listBookmarkIds(supabase, user.id).then((s) => { if (active) setIds(s); }).catch(() => {});
    return () => { active = false; };
  }, [supabase, user]);

  const signIn = useCallback(async () => {
    await supabase.auth.signInWithOAuth({
      provider: "google",
      options: { redirectTo: typeof window !== "undefined" ? window.location.origin : undefined },
    });
  }, [supabase]);

  const signOut = useCallback(async () => { await supabase.auth.signOut(); }, [supabase]);

  const toggle = useCallback(async (id: string) => {
    if (!user) { await signIn(); return; }
    const has = ids.has(id);
    // optimistic
    setIds((prev) => {
      const next = new Set(prev);
      if (has) next.delete(id); else next.add(id);
      return next;
    });
    try {
      if (has) await removeBookmark(supabase, user.id, id);
      else await addBookmark(supabase, user.id, id);
    } catch {
      // rollback on failure
      setIds((prev) => {
        const next = new Set(prev);
        if (has) next.add(id); else next.delete(id);
        return next;
      });
    }
  }, [supabase, user, ids, signIn]);

  const authValue = useMemo<AuthCtx>(() => ({ user, session, loading, signIn, signOut }),
    [user, session, loading, signIn, signOut]);
  const bmValue = useMemo<BookmarksCtx>(() => ({ ids, isScrapped: (id) => ids.has(id), toggle }),
    [ids, toggle]);

  return (
    <AuthContext.Provider value={authValue}>
      <BookmarksContext.Provider value={bmValue}>{children}</BookmarksContext.Provider>
    </AuthContext.Provider>
  );
}

export function useAuth(): AuthCtx {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used within AuthProvider");
  return ctx;
}
export function useBookmarks(): BookmarksCtx {
  const ctx = useContext(BookmarksContext);
  if (!ctx) throw new Error("useBookmarks must be used within AuthProvider");
  return ctx;
}
```

- [ ] **Step 4: Wrap the app in `layout.tsx`**

Modify `web/src/app/layout.tsx` to wrap everything (including `<Nav/>`) in `<AuthProvider>`:
```tsx
import { Nav } from "@/components/Nav";
import { AuthProvider } from "@/components/AuthProvider";
import "./globals.css";

export const metadata = {
  title: "FRAME — 전시 디스커버리",
  description: "사진·영상 전시를 찾고 둘러보세요",
  manifest: "/manifest.webmanifest",
};
export const viewport = { themeColor: "#000000" };

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="ko">
      <body>
        <AuthProvider>
          <Nav />
          <div className="pb-24 md:pb-0">{children}</div>
        </AuthProvider>
      </body>
    </html>
  );
}
```
(If Task 12 of Plan 2 hasn't added `manifest`/`viewport` yet, keep whatever metadata already exists and only add the `AuthProvider` wrapper.)

- [ ] **Step 5: Run test to verify it passes**

Run: `npm run test -- AuthProvider`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add web/src/components/AuthProvider.tsx web/src/components/AuthProvider.test.tsx web/src/app/layout.tsx
git commit -m "feat(web): auth + bookmarks context provider"
```

---

## Task 5: Functional ScrapButton

**Files:**
- Modify: `web/src/components/ScrapButton.tsx`
- Test: `web/src/components/ScrapButton.test.tsx`

The button now takes the exhibition `id`, reads scrapped state from `useBookmarks`, and toggles on click. It keeps the same visual styling so all existing call sites still look right. **Update call sites** that render `<ScrapButton />` to pass an id: `ExhibitionCard` (`exhibitionId={e.id}`), the detail page, and `SwipeDeck`'s ♡ action (the swipe ♡ should both scrap and advance).

- [ ] **Step 1: Write the failing test**

```tsx
// web/src/components/ScrapButton.test.tsx
import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

const toggle = vi.fn();
const ids = new Set<string>(["scrapped-1"]);
vi.mock("@/components/AuthProvider", () => ({
  useBookmarks: () => ({ ids, isScrapped: (id: string) => ids.has(id), toggle }),
}));

import { ScrapButton } from "@/components/ScrapButton";

describe("ScrapButton", () => {
  it("reflects scrapped state and toggles on click", () => {
    render(<ScrapButton exhibitionId="scrapped-1" />);
    const btn = screen.getByLabelText("스크랩 취소"); // already scrapped → aria reflects active
    fireEvent.click(btn);
    expect(toggle).toHaveBeenCalledWith("scrapped-1");
  });
  it("shows un-scrapped label when not saved", () => {
    render(<ScrapButton exhibitionId="other" />);
    expect(screen.getByLabelText("스크랩")).toBeInTheDocument();
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `npm run test -- ScrapButton`
Expected: FAIL — current `ScrapButton` takes `{ active }`, not `{ exhibitionId }`, and does not call `toggle`.

- [ ] **Step 3: Rewrite `ScrapButton`**

```tsx
// web/src/components/ScrapButton.tsx
"use client";
import { Heart } from "lucide-react";
import { useBookmarks } from "@/components/AuthProvider";

export function ScrapButton({
  exhibitionId,
  size = 15,
  className = "flex h-8 w-8 items-center justify-center rounded-full border border-line2 bg-black/45 text-white transition hover:bg-black/70",
}: {
  exhibitionId: string;
  size?: number;
  className?: string;
}) {
  const { isScrapped, toggle } = useBookmarks();
  const active = isScrapped(exhibitionId);
  return (
    <button
      type="button"
      aria-label={active ? "스크랩 취소" : "스크랩"}
      aria-pressed={active}
      onClick={(e) => {
        e.preventDefault(); // don't trigger the card's parent <Link>
        e.stopPropagation();
        void toggle(exhibitionId);
      }}
      className={className}
    >
      <Heart size={size} fill={active ? "currentColor" : "none"} />
    </button>
  );
}
```

- [ ] **Step 4: Update call sites to pass `exhibitionId`**

- `web/src/components/ExhibitionCard.tsx`: change `<ScrapButton />` to `<ScrapButton exhibitionId={e.id} />`.
- `web/src/app/exhibitions/[id]/page.tsx`: change `<ScrapButton />` to `<ScrapButton exhibitionId={e.id} />`.
- `web/src/components/SwipeDeck.tsx`: the ♡ action should scrap **and** advance. Replace the ♡ `<button aria-label="스크랩" ...>` with the functional component plus advance, e.g.:
  ```tsx
  <ScrapButton
    exhibitionId={current.id}
    size={22}
    className="flex h-16 w-16 items-center justify-center rounded-full bg-white text-black"
  />
  ```
  and keep a separate skip (✕) that only advances. To also advance on scrap, wrap: add `onClick`-after behavior by advancing in the deck — simplest is to leave ♡ as scrap-only and let ✕/tap advance; if you want scrap+advance, add a thin wrapper button that calls `toggle` via `useBookmarks` then `setI((n)=>n+1)`. (Either is acceptable; keep it consistent with the mockup where ♡ is the primary action.)

  Import at top of `SwipeDeck.tsx`: `import { ScrapButton } from "@/components/ScrapButton";` and remove the now-unused `Heart` import if it is no longer referenced.

- [ ] **Step 5: Run test + browser**

Run: `npm run test -- ScrapButton` → PASS.
Run full suite: `npm run test` → all green.
Run: `npm run dev`, open the home page while logged out → clicking a heart triggers Google login (via `toggle` → `signIn`). Log in, click a heart → it fills; reload → it stays filled (persisted). Stop server.

- [ ] **Step 6: Commit**

```bash
git add web/src/components/ScrapButton.tsx web/src/components/ScrapButton.test.tsx web/src/components/ExhibitionCard.tsx web/src/components/SwipeDeck.tsx web/src/app/exhibitions
git commit -m "feat(web): functional scrap button persisting to supabase"
```

---

## Task 6: Login button + auth state in Nav

**Files:**
- Create: `web/src/components/LoginButton.tsx`
- Modify: `web/src/components/Nav.tsx`
- Test: `web/src/components/LoginButton.test.tsx`

- [ ] **Step 1: Write the failing test**

```tsx
// web/src/components/LoginButton.test.tsx
import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

const signIn = vi.fn();
const signOut = vi.fn();
let mockUser: { email: string } | null = null;
vi.mock("@/components/AuthProvider", () => ({
  useAuth: () => ({ user: mockUser, session: null, loading: false, signIn, signOut }),
}));

import { LoginButton } from "@/components/LoginButton";

describe("LoginButton", () => {
  it("shows 로그인 and calls signIn when logged out", () => {
    mockUser = null;
    render(<LoginButton />);
    fireEvent.click(screen.getByText("로그인"));
    expect(signIn).toHaveBeenCalled();
  });
  it("shows the user email/menu when logged in", () => {
    mockUser = { email: "a@b.c" };
    render(<LoginButton />);
    expect(screen.getByText(/a@b\.c/)).toBeInTheDocument();
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `npm run test -- LoginButton`
Expected: FAIL — cannot find `@/components/LoginButton`.

- [ ] **Step 3: Write `LoginButton`**

```tsx
// web/src/components/LoginButton.tsx
"use client";
import { LogOut } from "lucide-react";
import { useAuth } from "@/components/AuthProvider";

export function LoginButton() {
  const { user, loading, signIn, signOut } = useAuth();
  if (loading) return <div className="h-9 w-20 animate-pulse rounded-md bg-panel2" />;
  if (!user) {
    return (
      <button onClick={() => void signIn()}
        className="rounded-md bg-white px-4 py-2 text-sm font-semibold text-black transition hover:bg-tx2">
        로그인
      </button>
    );
  }
  return (
    <div className="flex items-center gap-2">
      <span className="max-w-[160px] truncate text-sm text-tx2">{user.email}</span>
      <button onClick={() => void signOut()} aria-label="로그아웃"
        className="flex h-8 w-8 items-center justify-center rounded-md border border-line text-tx2 hover:text-tx">
        <LogOut size={15} />
      </button>
    </div>
  );
}
```

- [ ] **Step 4: Use it in `Nav.tsx`**

In `web/src/components/Nav.tsx`, replace the static desktop `<button ...>로그인</button>` with `<LoginButton />` (import it at the top: `import { LoginButton } from "@/components/LoginButton";`). Keep `ml-auto` placement by wrapping: `<div className="ml-auto"><LoginButton /></div>`.

- [ ] **Step 5: Run test + browser**

Run: `npm run test -- LoginButton` → PASS.
Run: `npm run dev` → desktop nav shows 로그인; after login it shows the email + logout. Stop server.

- [ ] **Step 6: Commit**

```bash
git add web/src/components/LoginButton.tsx web/src/components/LoginButton.test.tsx web/src/components/Nav.tsx
git commit -m "feat(web): login button + auth state in nav"
```

---

## Task 7: 스크랩 page

**Files:**
- Create: `web/src/app/scrap/page.tsx`

- [ ] **Step 1: Build the page**

Client component. Reads `useAuth` + `useBookmarks` + `loadCatalogSync`. Logged-out → a sign-in prompt. Logged-in → the catalog exhibitions whose id is in the bookmark Set, sorted closing-soon first (ongoing by ascending `endDate`, then others). Empty → a friendly empty state. Reuse `ExhibitionCard`.

```tsx
// web/src/app/scrap/page.tsx
"use client";
import { useMemo } from "react";
import { loadCatalogSync } from "@/lib/catalogClient";
import { useAuth, useBookmarks } from "@/components/AuthProvider";
import { ExhibitionCard } from "@/components/ExhibitionCard";
import { daysUntil } from "@/lib/status";

export default function ScrapPage() {
  const catalog = loadCatalogSync();
  const { user, loading, signIn } = useAuth();
  const { ids } = useBookmarks();
  const today = new Date();

  const saved = useMemo(() => {
    const list = catalog.exhibitions.filter((e) => ids.has(e.id));
    const rank = (d: number | null) => (d == null ? Number.POSITIVE_INFINITY : d < 0 ? 1e6 - d : d);
    return list.sort((a, b) => rank(daysUntil(a.endDate, today)) - rank(daysUntil(b.endDate, today)));
  }, [catalog.exhibitions, ids, today]);

  if (loading) return <main className="mx-auto max-w-[1180px] px-7 py-16 text-tx3">불러오는 중…</main>;
  if (!user) {
    return (
      <main className="mx-auto max-w-[1180px] px-7 py-20 text-center">
        <h1 className="text-2xl font-extrabold tracking-tight">스크랩</h1>
        <p className="mt-3 text-tx2">로그인하면 마음에 드는 전시를 저장할 수 있어요.</p>
        <button onClick={() => void signIn()}
          className="mt-6 rounded-md bg-white px-5 py-2.5 text-sm font-semibold text-black">
          Google로 로그인
        </button>
      </main>
    );
  }
  return (
    <main className="mx-auto max-w-[1180px] px-7 py-8">
      <h1 className="text-[28px] font-extrabold tracking-tight">스크랩</h1>
      <p className="mt-2 text-sm text-tx3">{saved.length}건 · 종료 임박순</p>
      {saved.length === 0 ? (
        <div className="py-20 text-center text-tx3">아직 스크랩한 전시가 없어요</div>
      ) : (
        <div className="mt-6 grid grid-cols-2 gap-4 md:grid-cols-4">
          {saved.map((e) => <ExhibitionCard key={e.id} exhibition={e} today={today} />)}
        </div>
      )}
    </main>
  );
}
```

- [ ] **Step 2: Browser verify**

Run: `npm run dev`, open http://localhost:3000/scrap logged out → prompt. Log in, scrap a couple of exhibitions from home, return to /scrap → they appear, closing-soon first. Unscrap one → it disappears. Stop server.

- [ ] **Step 3: Commit**

```bash
git add web/src/app/scrap
git commit -m "feat(web): scrap page (saved exhibitions, closing-soon order)"
```

---

## Task 8: 마이 page

**Files:**
- Create: `web/src/app/me/page.tsx`

- [ ] **Step 1: Build the page**

Client component. Logged-out → sign-in prompt. Logged-in → show email, scrap count, a sign-out button, and a placeholder card linking to subscription settings ("구독 설정 — 곧 제공" until Plan 4 adds it). Keep it minimal and on-tone.

```tsx
// web/src/app/me/page.tsx
"use client";
import { useAuth, useBookmarks } from "@/components/AuthProvider";

export default function MePage() {
  const { user, loading, signIn, signOut } = useAuth();
  const { ids } = useBookmarks();

  if (loading) return <main className="mx-auto max-w-[680px] px-7 py-16 text-tx3">불러오는 중…</main>;
  if (!user) {
    return (
      <main className="mx-auto max-w-[680px] px-7 py-20 text-center">
        <h1 className="text-2xl font-extrabold tracking-tight">마이</h1>
        <p className="mt-3 text-tx2">로그인하고 전시를 저장하고 알림을 받아보세요.</p>
        <button onClick={() => void signIn()}
          className="mt-6 rounded-md bg-white px-5 py-2.5 text-sm font-semibold text-black">
          Google로 로그인
        </button>
      </main>
    );
  }
  return (
    <main className="mx-auto max-w-[680px] px-7 py-10">
      <h1 className="text-[28px] font-extrabold tracking-tight">마이</h1>
      <div className="mt-6 rounded-lg border border-line p-5">
        <div className="text-sm text-tx3">계정</div>
        <div className="mt-1 text-base">{user.email}</div>
        <div className="mt-4 flex items-center gap-6 text-sm text-tx2">
          <span>스크랩 <b className="text-tx">{ids.size}</b></span>
        </div>
      </div>
      <div className="mt-4 rounded-lg border border-line p-5 text-sm text-tx3">
        구독 설정 — 곧 제공
      </div>
      <button onClick={() => void signOut()}
        className="mt-6 rounded-md border border-line2 px-4 py-2 text-sm font-medium hover:bg-panel2">
        로그아웃
      </button>
    </main>
  );
}
```

- [ ] **Step 2: Browser verify**

Run: `npm run dev`, open http://localhost:3000/me → logged out prompt; after login shows email + scrap count + logout. Logout returns to prompt. Stop server.

- [ ] **Step 3: Commit**

```bash
git add web/src/app/me
git commit -m "feat(web): my page (account + sign out)"
```

---

## Self-Review (completed during planning)

**Spec coverage:**
- §5.2 user plane (Supabase, Google OAuth, RLS) → Tasks 1–2, 4.
- §7 DB model: `profiles`, `bookmarks` with `auth.uid() = user_id` RLS → Task 2. (`subscriptions`, `email_log` are Plan 4.)
- IA: 스크랩 page (Task 7), 마이 page (Task 8), login state in Nav (Task 6) — the routes that 404'd in Plan 2 are now real.

**Placeholder scan:** No TBD/TODO. The 마이 "구독 설정 — 곧 제공" card is an intentional, labeled stub filled by Plan 4. The SQL migration is complete and runnable.

**Type consistency:**
- Reuses Plan 2's `Exhibition` / `loadCatalogSync` / `ExhibitionCard` unchanged.
- `ScrapButton` signature changes from `{ active?: boolean }` (Plan 2, visual-only) to `{ exhibitionId: string; size?; className? }` — every call site (ExhibitionCard, detail page, SwipeDeck) is updated in Task 5, Step 4.
- `useBookmarks()` returns `{ ids: Set<string>, isScrapped, toggle }` — consistent across AuthProvider (Task 4), ScrapButton (Task 5), scrap page (Task 7), me page (Task 8).
- `bookmarks.ts` functions take `(client, userId, exhibitionId)` — consistent between definition (Task 3) and use in AuthProvider (Task 4).

**Static-export safety:** all Supabase usage is in `"use client"` components; OAuth uses PKCE + `detectSessionInUrl`, so no server route handler is needed and `output: "export"` from Plan 2 still holds.

**Known follow-ups (not gaps):** subscription settings UI + email jobs (Plan 4) read the same `bookmarks` table and a new `subscriptions`/`email_log` schema.
