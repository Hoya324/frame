# 필터·정렬 통일 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: superpowers:subagent-driven-development. Steps use `- [ ]` checkboxes.

**Goal:** 둘러보기·검색·스크랩·지도(+공간시트)에 동일한 상태 필터(진행중·예정·종료) + 정렬(추천·마감임박·최신, 지도는 가까운 순) 컨벤션과 칩 디자인을 적용한다.

**Architecture:** 정렬은 `lib/sort.ts`의 순수 `sortExhibitions`로 일원화, 거리 계산은 `lib/geo.ts`로 추출. 공용 표시 컴포넌트 `controls/FilterGroup`·`controls/SortChips` + 기존 `FilterChips`로 각 페이지가 일관된 컨트롤 바를 조립. 상태 필터는 기존 `applyFilters` 재사용.

**Tech Stack:** Next.js 16, React 19, Tailwind v4, vitest + @testing-library/react.

작업 디렉터리 `web/`. 테스트 `cd web && npx vitest run <경로>`. 상세 근거는 `docs/superpowers/specs/2026-06-02-filter-sort-unification-design.md` 참고.

---

## Task 1: `lib/geo.ts` — 거리 계산 추출

**Files:** Create `web/src/lib/geo.ts`, `web/src/lib/geo.test.ts`

- [ ] **Step 1: 테스트 작성** `web/src/lib/geo.test.ts`

```ts
import { describe, expect, it } from "vitest";
import { distanceKm } from "@/lib/geo";

describe("distanceKm", () => {
  it("is zero for identical points", () => {
    expect(distanceKm([126.98, 37.57], [126.98, 37.57])).toBeCloseTo(0, 5);
  });
  it("approximates Seoul→Busan (~325km)", () => {
    const d = distanceKm([126.978, 37.566], [129.075, 35.18]);
    expect(d).toBeGreaterThan(300);
    expect(d).toBeLessThan(340);
  });
});
```

- [ ] **Step 2: 실패 확인** `cd web && npx vitest run src/lib/geo.test.ts` → FAIL

- [ ] **Step 3: 구현** `web/src/lib/geo.ts` (기존 `map/page.tsx`의 `distanceKm`와 동일 공식, `[lng, lat]` 입력)

```ts
// [lng, lat] 두 좌표 사이의 대략적 거리(km), Haversine.
export function distanceKm(a: [number, number], b: [number, number]): number {
  const R = 6371;
  const toRad = (d: number) => (d * Math.PI) / 180;
  const dLat = toRad(b[1] - a[1]);
  const dLng = toRad(b[0] - a[0]);
  const s =
    Math.sin(dLat / 2) ** 2 +
    Math.cos(toRad(a[1])) * Math.cos(toRad(b[1])) * Math.sin(dLng / 2) ** 2;
  return 2 * R * Math.asin(Math.sqrt(s));
}
```

- [ ] **Step 4: 통과 확인** → PASS
- [ ] **Step 5: 커밋** `git add web/src/lib/geo.ts web/src/lib/geo.test.ts && git commit -m "feat(web): extract distanceKm into lib/geo"`

---

## Task 2: `lib/sort.ts` — 공통 정렬

**Files:** Create `web/src/lib/sort.ts`, `web/src/lib/sort.test.ts`

- [ ] **Step 1: 테스트 작성** `web/src/lib/sort.test.ts`

```ts
import { describe, expect, it } from "vitest";
import { sortExhibitions } from "@/lib/sort";
import type { Exhibition } from "@/lib/catalog";

function ex(p: Partial<Exhibition> & { id: string }): Exhibition {
  return {
    id: p.id, source: null, title: p.id, posterImageUrl: null, description: null,
    medium: null, exhibitionType: null, genreTags: [], feeType: null, priceMin: null, priceMax: null,
    startDate: p.startDate ?? null, endDate: p.endDate ?? null, status: p.status ?? "unknown",
    openHours: null, venue: p.venue ?? null, artists: [], sourceUrl: null,
    featured: p.featured ?? false, popularityScore: p.popularityScore ?? null, lang: null, tr: {},
  };
}
const v = (lng: number, lat: number) => ({ id: "v", name: "v", region: null, district: null, lat, lng, lang: null, tr: {} });

const ITEMS = [
  ex({ id: "past", status: "past", startDate: "2026-01-01", endDate: "2026-02-01", popularityScore: 9 }),
  ex({ id: "soon", status: "ongoing", startDate: "2026-05-01", endDate: "2026-06-05" }),
  ex({ id: "later", status: "ongoing", startDate: "2026-05-20", endDate: "2026-07-01" }),
  ex({ id: "up", status: "upcoming", startDate: "2026-08-01", endDate: "2026-09-01" }),
  ex({ id: "feat", status: "ongoing", startDate: "2026-04-01", endDate: "2026-12-01", featured: true, popularityScore: 1 }),
];

describe("sortExhibitions", () => {
  it("recommended puts featured first, then by popularity", () => {
    const ids = sortExhibitions(ITEMS, "recommended").map((e) => e.id);
    expect(ids[0]).toBe("feat");
  });
  it("closing puts soonest-ending ongoing first, ended last", () => {
    const ids = sortExhibitions(ITEMS, "closing").map((e) => e.id);
    expect(ids[0]).toBe("soon");
    expect(ids[ids.length - 1]).toBe("past");
  });
  it("recent orders by newest start date", () => {
    const ids = sortExhibitions(ITEMS, "recent").map((e) => e.id);
    expect(ids[0]).toBe("up");
  });
  it("nearby orders by distance from userLoc; falls back to recommended without it", () => {
    const near = ex({ id: "near", status: "ongoing", venue: v(127.0, 37.5) });
    const far = ex({ id: "far", status: "ongoing", venue: v(135.0, 34.0) });
    const ids = sortExhibitions([far, near], "nearby", { userLoc: [127.0, 37.5] }).map((e) => e.id);
    expect(ids[0]).toBe("near");
    // userLoc 없으면 recommended 폴백(throw 안 함)
    expect(() => sortExhibitions([far, near], "nearby")).not.toThrow();
  });
  it("does not mutate input", () => {
    const copy = [...ITEMS];
    sortExhibitions(ITEMS, "recent");
    expect(ITEMS.map((e) => e.id)).toEqual(copy.map((e) => e.id));
  });
});
```

- [ ] **Step 2: 실패 확인** → FAIL
- [ ] **Step 3: 구현** `web/src/lib/sort.ts`

```ts
import type { Exhibition, Status } from "@/lib/catalog";
import { distanceKm } from "@/lib/geo";

export type SortKey = "recommended" | "closing" | "recent" | "nearby";

export interface SortContext {
  today?: Date;
  userLoc?: [number, number] | null;
}

const STATUS_RANK: Record<Status, number> = { ongoing: 0, upcoming: 1, unknown: 2, past: 3 };

function byRecommended(a: Exhibition, b: Exhibition): number {
  if (a.featured !== b.featured) return a.featured ? -1 : 1;
  const ap = a.popularityScore ?? -Infinity;
  const bp = b.popularityScore ?? -Infinity;
  if (ap !== bp) return bp - ap;
  if (STATUS_RANK[a.status] !== STATUS_RANK[b.status]) return STATUS_RANK[a.status] - STATUS_RANK[b.status];
  return (b.startDate ?? "").localeCompare(a.startDate ?? "");
}

export function sortExhibitions(items: Exhibition[], key: SortKey, ctx: SortContext = {}): Exhibition[] {
  const copy = [...items];
  if (key === "recommended") {
    copy.sort(byRecommended);
  } else if (key === "closing") {
    copy.sort((a, b) => {
      const ao = a.status === "ongoing" ? 0 : 1;
      const bo = b.status === "ongoing" ? 0 : 1;
      if (ao !== bo) return ao - bo;
      return (a.endDate ?? "9999-99-99").localeCompare(b.endDate ?? "9999-99-99");
    });
  } else if (key === "recent") {
    copy.sort((a, b) => (b.startDate ?? "").localeCompare(a.startDate ?? ""));
  } else {
    // nearby
    const loc = ctx.userLoc;
    if (!loc) return sortExhibitions(items, "recommended", ctx);
    const dist = (e: Exhibition) =>
      e.venue?.lat != null && e.venue?.lng != null
        ? distanceKm(loc, [e.venue.lng, e.venue.lat])
        : Infinity;
    copy.sort((a, b) => dist(a) - dist(b));
  }
  return copy;
}
```

- [ ] **Step 4: 통과 확인** → PASS
- [ ] **Step 5: 커밋** `git add web/src/lib/sort.ts web/src/lib/sort.test.ts && git commit -m "feat(web): unified sortExhibitions (recommended/closing/recent/nearby)"`

---

## Task 3: i18n 키 (controls.* / sort.*) 추가 + venue 키 마이그레이션

**Files:** Modify `web/src/lib/i18n.ts`

기존 `venue.statusLabel`/`venue.sortLabel`/`venue.sortClosing`/`venue.sortRecent` 줄을 각 로케일에서 아래로 **교체**(키 이름 변경 + 신규 추가). 값은 로케일별로 맞춘다.

- [ ] **Step 1: ko 블록** — `"venue.statusLabel"`~`"venue.sortRecent"` 4줄을 다음으로 교체:

```ts
  "controls.status": "상태",
  "controls.sort": "정렬",
  "controls.more": "그 외",
  "sort.recommended": "추천순",
  "sort.closing": "마감임박",
  "sort.recent": "최신순",
  "sort.nearby": "가까운 순",
```

- [ ] **Step 2: en 블록** — 동일 위치 4줄 교체:

```ts
  "controls.status": "Status",
  "controls.sort": "Sort",
  "controls.more": "More",
  "sort.recommended": "Recommended",
  "sort.closing": "Closing soon",
  "sort.recent": "Newest",
  "sort.nearby": "Nearest",
```

- [ ] **Step 3: ja 블록** — 동일 위치 4줄 교체:

```ts
  "controls.status": "状態",
  "controls.sort": "並び替え",
  "controls.more": "その他",
  "sort.recommended": "おすすめ順",
  "sort.closing": "終了間近",
  "sort.recent": "新着順",
  "sort.nearby": "近い順",
```

- [ ] **Step 4: 확인** `cd web && npx tsc --noEmit && npx eslint src/lib/i18n.ts` → clean. (이 시점엔 `venue.sortLabel` 등을 쓰는 `VenueSheet.tsx`가 깨질 수 있음 — Task 5에서 함께 맞춘다. 빌드가 깨지면 Task 5 후 재확인.)
- [ ] **Step 5: 커밋** `git add web/src/lib/i18n.ts && git commit -m "feat(web): canonical controls.* / sort.* i18n keys"`

---

## Task 4: 공용 컨트롤 컴포넌트 `FilterGroup` + `SortChips`

**Files:** Create `web/src/components/controls/FilterGroup.tsx`, `web/src/components/controls/SortChips.tsx`, `web/src/components/controls/SortChips.test.tsx`

- [ ] **Step 1: `FilterGroup.tsx`** (라벨 + 칩 줄 래퍼)

```tsx
"use client";
export function FilterGroup({ label, children }: { label?: string; children: React.ReactNode }) {
  return (
    <div className="flex flex-wrap items-center gap-2">
      {label ? <span className="shrink-0 text-[11px] text-tx3">{label}</span> : null}
      {children}
    </div>
  );
}
```

- [ ] **Step 2: 테스트 작성** `web/src/components/controls/SortChips.test.tsx`

```tsx
import { screen, fireEvent } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { renderWithLang } from "@/test/lang";
import { SortChips } from "@/components/controls/SortChips";

describe("SortChips", () => {
  it("renders the given options and marks the active one", () => {
    renderWithLang(<SortChips value="recommended" options={["recommended", "closing", "recent"]} onChange={vi.fn()} />);
    const rec = screen.getByRole("button", { name: "추천순" });
    expect(rec).toHaveAttribute("aria-pressed", "true");
    expect(screen.getByRole("button", { name: "마감임박" })).toHaveAttribute("aria-pressed", "false");
  });
  it("calls onChange with the picked key", () => {
    const onChange = vi.fn();
    renderWithLang(<SortChips value="recommended" options={["recommended", "recent"]} onChange={onChange} />);
    fireEvent.click(screen.getByRole("button", { name: "최신순" }));
    expect(onChange).toHaveBeenCalledWith("recent");
  });
});
```

- [ ] **Step 3: 실패 확인** → FAIL
- [ ] **Step 4: `SortChips.tsx`** (단일 선택, 공통 칩 스타일)

```tsx
"use client";
import { useLang } from "@/components/LanguageProvider";
import type { SortKey } from "@/lib/sort";

const KEY_I18N: Record<SortKey, string> = {
  recommended: "sort.recommended",
  closing: "sort.closing",
  recent: "sort.recent",
  nearby: "sort.nearby",
};

export function SortChips({
  value, options, onChange, disabled,
}: {
  value: SortKey;
  options: SortKey[];
  onChange: (key: SortKey) => void;
  disabled?: Partial<Record<SortKey, boolean>>;
}) {
  const { t } = useLang();
  return (
    <div className="flex flex-wrap gap-2">
      {options.map((k) => {
        const on = value === k;
        const off = disabled?.[k];
        return (
          <button
            key={k}
            type="button"
            disabled={off}
            onClick={() => onChange(k)}
            aria-pressed={on}
            className={`rounded-full px-3.5 py-1.5 text-[13px] font-medium transition disabled:opacity-40 ${
              on ? "border border-white bg-white font-semibold text-black"
                 : "border border-line text-tx2 hover:text-tx"
            }`}
          >
            {t(KEY_I18N[k])}
          </button>
        );
      })}
    </div>
  );
}
```

- [ ] **Step 5: 통과 확인** `cd web && npx vitest run src/components/controls/SortChips.test.tsx` → PASS
- [ ] **Step 6: 커밋** `git add web/src/components/controls && git commit -m "feat(web): shared FilterGroup + SortChips controls"`

---

## Task 5: 공간시트 — 공통 키/스타일로 통일 + 정렬 위임

**Files:** Modify `web/src/components/VenueSheet.tsx`, `web/src/lib/venueSheet.ts`, `web/src/components/VenueSheet.test.tsx`

- [ ] **Step 1: `venueSheet.ts`의 `sortForSheet`를 `sortExhibitions` 위임으로 교체**

`web/src/lib/venueSheet.ts`에서 `sortForSheet` 구현 본문을 다음으로 교체(시그니처/타입 `SortMode = "closing" | "recent"` 유지):

```ts
import { sortExhibitions } from "@/lib/sort";
// ...
export function sortForSheet(items: Exhibition[], mode: SortMode): Exhibition[] {
  return sortExhibitions(items, mode);
}
```

기존 `STATUS_RANK`/closing/recent 정렬 블록은 제거(중복). `venueSummary`, `filterByStatus`, `nextSnap`은 유지. `venueSheet.test.ts`의 closing/recent 기대값은 동일하므로 그대로 통과해야 한다 — 실행해 확인.

- [ ] **Step 2: `VenueSheet.tsx` 라벨 키 교체**

- `t("venue.statusLabel")` → `t("controls.status")`
- `t("venue.sortLabel")` → `t("controls.sort")`
- `SORTS` 배열의 키: `{ mode: "closing", key: "venue.sortClosing" }` → `key: "sort.closing"`, `{ mode: "recent", key: "venue.sortRecent" }` → `key: "sort.recent"`

- [ ] **Step 3: 칩 스타일 통일**

`VenueSheet.tsx`의 상태 필터 칩과 정렬 칩 className을 공통 스타일로 교체(현재 `rounded-full px-3 py-1 text-xs font-semibold ...`):

```
rounded-full px-3.5 py-1.5 text-[13px] font-medium transition
```
활성: `border border-white bg-white font-semibold text-black`, 비활성: `border border-line text-tx2 hover:text-tx`. (두 칩 그룹 모두)

- [ ] **Step 4: 확인** `cd web && npx tsc --noEmit && npx eslint src/components/VenueSheet.tsx src/lib/venueSheet.ts && npx vitest run src/components/VenueSheet.test.tsx src/lib/venueSheet.test.ts` → 전부 통과
- [ ] **Step 5: 커밋** `git add web/src/components/VenueSheet.tsx web/src/lib/venueSheet.ts && git commit -m "refactor(web): venue sheet uses shared sort + unified chip style/keys"`

---

## Task 6: 스크랩 페이지 — 상태 필터 + 정렬 추가

**Files:** Modify `web/src/app/scrap/page.tsx`

기존: 북마크 목록을 마감순 하드코딩. 변경: 상태 필터(진행중·예정·종료) + 정렬(추천·마감임박(기본)·최신).

- [ ] **Step 1: import + 상태 추가**

```tsx
import { useMemo, useState } from "react";
import { applyFilters, type FilterState } from "@/lib/filters";
import { sortExhibitions, type SortKey } from "@/lib/sort";
import { FilterChips } from "@/components/FilterChips";
import { FilterGroup } from "@/components/controls/FilterGroup";
import { SortChips } from "@/components/controls/SortChips";
```

컴포넌트 안에 상태:

```tsx
  const [statuses, setStatuses] = useState<string[]>([]);
  const [sort, setSort] = useState<SortKey>("closing");
  const toggleStatus = (v: string) =>
    setStatuses((s) => (s.includes(v) ? s.filter((x) => x !== v) : [...s, v]));
```

- [ ] **Step 2: `saved` 계산을 필터+정렬로 교체**

```tsx
  const saved = useMemo(() => {
    const base = catalog.exhibitions.filter((e) => ids.has(e.id));
    const f: FilterState = {
      statuses: statuses as FilterState["statuses"], mediums: [], types: [], freeOnly: false, regions: [],
    };
    return sortExhibitions(applyFilters(base, f), sort, { today });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [catalog.exhibitions, ids, statuses, sort]);
```

- [ ] **Step 3: 컨트롤 바 렌더**

로그인된 뷰의 `<h1>`/subtitle 다음, 그리드 위에 추가:

```tsx
      <div className="mt-5 flex flex-wrap items-center gap-x-3 gap-y-2">
        <FilterGroup label={t("controls.status")}>
          <FilterChips active={statuses} onToggle={toggleStatus} options={[
            { value: "ongoing", label: t("filter.ongoing") },
            { value: "upcoming", label: t("filter.upcoming") },
            { value: "past", label: t("filter.past") },
          ]} />
        </FilterGroup>
        <span className="h-4 w-px bg-line2" aria-hidden="true" />
        <FilterGroup label={t("controls.sort")}>
          <SortChips value={sort} options={["recommended", "closing", "recent"]} onChange={setSort} />
        </FilterGroup>
      </div>
```

빈 상태(`saved.length === 0`) 분기는 유지하되, 필터로 0건이 될 수 있으므로 메시지는 기존 `scrap.empty` 재사용.

- [ ] **Step 4: 확인** `cd web && npx tsc --noEmit && npx eslint src/app/scrap/page.tsx && npx vitest run` → 통과
- [ ] **Step 5: 커밋** `git add web/src/app/scrap/page.tsx && git commit -m "feat(web): status filter + sort on scrap page"`

---

## Task 7: 검색 페이지 — 정렬 추가 + 그룹 라벨 정리

**Files:** Modify `web/src/app/search/page.tsx`

상태(진행중·예정·종료)/그 외(사진·영상·장비·개인전·단체전·무료)/지역은 유지하되 `상태`·`그 외` 라벨로 그룹화하고, 정렬(추천·마감·최신)을 추가. 검색 결과를 정렬한다.

- [ ] **Step 1: import + 정렬 상태**

```tsx
import { sortExhibitions, type SortKey } from "@/lib/sort";
import { FilterGroup } from "@/components/controls/FilterGroup";
import { SortChips } from "@/components/controls/SortChips";
```

컴포넌트 안:

```tsx
  const [sort, setSort] = useState<SortKey>("recommended");
```

- [ ] **Step 2: 결과 정렬**

```tsx
  const results = sortExhibitions(searchExhibitions(applyFilters(catalog.exhibitions, f), q), sort);
```

- [ ] **Step 3: 필터 칩을 라벨 그룹으로 분리 + 정렬 추가**

기존 단일 `FilterChips`(상태+그 외 혼합) 블록을 다음으로 교체:

```tsx
      <div className="mb-3 flex flex-wrap items-center gap-x-3 gap-y-2">
        <FilterGroup label={t("controls.status")}>
          <FilterChips active={chips} onToggle={toggle} options={[
            { value: "ongoing", label: t("filter.ongoing") },
            { value: "upcoming", label: t("filter.upcoming") },
            { value: "past", label: t("filter.past") },
          ]} />
        </FilterGroup>
        <span className="h-4 w-px bg-line2" aria-hidden="true" />
        <FilterGroup label={t("controls.more")}>
          <FilterChips active={chips} onToggle={toggle} options={[
            { value: "photo", label: t("filter.photo") },
            { value: "video", label: t("filter.video") },
            { value: "gear", label: t("filter.gear") },
            { value: "solo", label: t("filter.solo") },
            { value: "group", label: t("filter.group") },
            { value: "free", label: t("filter.free") },
          ]} />
        </FilterGroup>
        <span className="h-4 w-px bg-line2" aria-hidden="true" />
        <FilterGroup label={t("controls.sort")}>
          <SortChips value={sort} options={["recommended", "closing", "recent"]} onChange={setSort} />
        </FilterGroup>
      </div>
```

지역 그룹(`cityGroups.map`)은 유지하되, 각 그룹의 `<span className="shrink-0 text-xs text-tx3">{g.country}</span>` 라벨 스타일을 `text-[11px]`로 맞춘다(통일).

- [ ] **Step 4: 확인** `cd web && npx tsc --noEmit && npx eslint src/app/search/page.tsx && npx vitest run` → 통과
- [ ] **Step 5: 커밋** `git add web/src/app/search/page.tsx && git commit -m "feat(web): sort + grouped filter labels on search page"`

---

## Task 8: 둘러보기(홈) — 상태 필터 통일 + 정렬 추가

**Files:** Modify `web/src/app/page.tsx`

홈은 섹션형(featured hero + 곧 종료 + 진행중). 변경: 상태 필터를 진행중·예정·종료로 통일(곧 종료 제거), 그 외(무료·사진·개인전) 유지, **정렬(추천·마감·최신)을 추가하고 메인 목록을 단일 정렬 그리드로 노출**. featured hero와 "곧 종료" 큐레이션 섹션은 유지(추천 진입점). 정렬/상태 필터는 그 아래 메인 목록에 적용.

- [ ] **Step 1: import 교체** — `isClosingSoon`는 큐레이션 섹션용으로 유지. 추가:

```tsx
import { sortExhibitions, type SortKey } from "@/lib/sort";
import { FilterGroup } from "@/components/controls/FilterGroup";
import { SortChips } from "@/components/controls/SortChips";
```

- [ ] **Step 2: 상태 옵션/정렬 상태 정리**

`STATUS_OPTS`를 진행중·예정·종료로 교체, `chips` status 매핑에 `past` 포함, 정렬 상태 추가:

```tsx
  const STATUS_OPTS = [
    { value: "ongoing", label: t("filter.ongoing") },
    { value: "upcoming", label: t("filter.upcoming") },
    { value: "past", label: t("filter.past") },
  ];
  const EXTRA_OPTS = [
    { value: "free", label: t("filter.free") },
    { value: "photo", label: t("filter.photo") },
    { value: "solo", label: t("filter.solo") },
  ];
  const [sort, setSort] = useState<SortKey>("recommended");
```

`f`의 statuses 매핑을 `["ongoing", "upcoming", "past"]` 포함으로:

```tsx
    statuses: chips.filter((c) => ["ongoing", "upcoming", "past"].includes(c)) as FilterState["statuses"],
```

`closing` 관련 분기(`if (chips.includes("closing")) ...`)는 제거.

- [ ] **Step 3: 메인 목록 정렬 적용**

`const ongoing = list.filter((e) => e.status === "ongoing");` 를, 필터된 전체를 정렬한 메인 목록으로 교체:

```tsx
  const mainList = sortExhibitions(list, sort, { today });
```

- [ ] **Step 4: time 모드 렌더 수정**

time 모드 필터 바를 라벨 그룹 + 정렬로 교체:

```tsx
          <div className="flex flex-wrap items-center gap-x-3 gap-y-2 pb-7">
            <FilterGroup label={t("controls.status")}>
              <FilterChips options={STATUS_OPTS} active={chips} onToggle={toggle} />
            </FilterGroup>
            <span className="h-4 w-px bg-line2" aria-hidden="true" />
            <FilterGroup label={t("controls.more")}>
              <FilterChips options={EXTRA_OPTS} active={chips} onToggle={toggle} />
            </FilterGroup>
            <span className="h-4 w-px bg-line2" aria-hidden="true" />
            <FilterGroup label={t("controls.sort")}>
              <SortChips value={sort} options={["recommended", "closing", "recent"]} onChange={setSort} />
            </FilterGroup>
          </div>
```

featured hero, 곧 종료 큐레이션 섹션은 그대로 두고, 마지막 `Section`을 메인 목록으로 교체:

```tsx
          <Section title={t("home.sectionOngoing")} hint={t("home.sectionOngoingHint")}>
            {mainList.map((e) => <ExhibitionCard key={e.id} exhibition={e} today={today} />)}
          </Section>
```

(섹션 제목은 기존 키 재사용. 메인 목록이 상태 필터/정렬 결과를 반영.)

swipe 모드는 기존대로 `EXTRA_OPTS` + `ongoing` 사용하되, `ongoing`이 제거됐으므로 swipe용 목록을 `list.filter((e) => e.status === "ongoing")`로 인라인 정의:

```tsx
            <SwipeDeck key={chips.join(",")} items={list.filter((e) => e.status === "ongoing")} />
```

- [ ] **Step 5: 확인** `cd web && npx tsc --noEmit && npx eslint src/app/page.tsx && npx vitest run` → 통과
- [ ] **Step 6: 커밋** `git add web/src/app/page.tsx && git commit -m "feat(web): unify status filter + add sort on discover page"`

---

## Task 9: 지도 — 상태 필터 + 정렬(가까운 순)

**Files:** Modify `web/src/app/map/page.tsx`

지역 칩 유지 + 상태 필터(진행중·예정·종료) 추가(마커/클러스터 `items`와 사이드바 둘 다 반영) + 정렬(추천·마감·최신·가까운 순). 위치 켜지면 정렬을 `nearby`로 전환. 기존 `distanceKm`는 `lib/geo`에서 import로 교체.

- [ ] **Step 1: import 교체/추가**

파일 상단 로컬 `distanceKm` 함수(약 L16-25) 제거하고:

```tsx
import { distanceKm } from "@/lib/geo";
import { applyFilters, type FilterState } from "@/lib/filters";
import { sortExhibitions, type SortKey } from "@/lib/sort";
import { FilterGroup } from "@/components/controls/FilterGroup";
import { SortChips } from "@/components/controls/SortChips";
```

- [ ] **Step 2: 상태 추가**

```tsx
  const [statuses, setStatuses] = useState<string[]>([]);
  const [sort, setSort] = useState<SortKey>("recommended");
  const toggleStatus = (v: string) =>
    setStatuses((s) => (s.includes(v) ? s.filter((x) => x !== v) : [...s, v]));
```

- [ ] **Step 3: `items`에 상태 필터 적용** (마커/클러스터/사이드바 공통 소스)

`items` useMemo의 결과에 상태 필터를 적용. 기존:

```tsx
  const items = useMemo(
    () =>
      mappable
        .filter(({ bucket }) => cities.length === 0 || (bucket && cities.includes(bucket.city)))
        .map(({ e }) => e),
    [mappable, cities],
  );
```

교체:

```tsx
  const items = useMemo(() => {
    const base = mappable
      .filter(({ bucket }) => cities.length === 0 || (bucket && cities.includes(bucket.city)))
      .map(({ e }) => e);
    const f: FilterState = {
      statuses: statuses as FilterState["statuses"], mediums: [], types: [], freeOnly: false, regions: [],
    };
    return applyFilters(base, f);
  }, [mappable, cities, statuses]);
```

- [ ] **Step 4: 사이드바 `listed` 정렬을 `sortExhibitions`로 교체**

기존 `listed` useMemo의 `userLoc` 거리 정렬 분기를 정렬 상태 기반으로 교체:

```tsx
  const listed = useMemo(() => {
    const base = visibleIds ? items.filter((e) => visibleIds.has(e.id)) : items;
    return sortExhibitions(base, sort, { userLoc: userLoc ?? undefined });
  }, [items, visibleIds, userLoc, sort]);
```

(기존 `distanceKm` 인라인 정렬 제거.)

- [ ] **Step 5: 위치 켜지면 정렬을 nearby로**

`locate()`의 성공 콜백에서 `setUserLoc(...)` 다음 줄에 `setSort("nearby");` 추가.

- [ ] **Step 6: 컨트롤 바 렌더** — 지역 칩 블록 다음(위치 버튼 줄 위/아래 적절한 곳)에 상태/정렬 그룹 추가:

```tsx
      <div className="mb-3 flex flex-wrap items-center gap-x-3 gap-y-2">
        <FilterGroup label={t("controls.status")}>
          <FilterChips active={statuses} onToggle={toggleStatus} options={[
            { value: "ongoing", label: t("filter.ongoing") },
            { value: "upcoming", label: t("filter.upcoming") },
            { value: "past", label: t("filter.past") },
          ]} />
        </FilterGroup>
        <span className="h-4 w-px bg-line2" aria-hidden="true" />
        <FilterGroup label={t("controls.sort")}>
          <SortChips
            value={sort}
            options={["recommended", "closing", "recent", "nearby"]}
            onChange={setSort}
            disabled={{ nearby: !userLoc }}
          />
        </FilterGroup>
      </div>
```

- [ ] **Step 7: 확인** `cd web && npx tsc --noEmit && npx eslint src/app/map/page.tsx && npx vitest run && npx next build` → 전부 통과
- [ ] **Step 8: 커밋** `git add web/src/app/map/page.tsx && git commit -m "feat(web): status filter + sort (incl. nearby) on map page"`

---

## Task 10: 수동 검증 (실제 앱)

- [ ] dev 서버에서 각 페이지 확인:
  - 둘러보기/검색/스크랩/지도/공간시트의 칩 디자인이 동일(크기/색)
  - 상태 필터 = 진행중·예정·종료, 정렬 = 추천·마감임박·최신(지도는 +가까운 순)
  - 상태 필터 적용 시 목록/마커 변화, 정렬 전환 시 순서 변화
  - 지도: 위치 켜면 가까운 순으로 전환, 상태 필터가 마커+사이드바 동시 반영
  - 공간시트 회귀 없음
- [ ] 문제 없으면 완료. 회귀 시 superpowers:systematic-debugging.

## 완료 기준
- `cd web && npx vitest run` 전부 통과 + `npx next build` 성공
- 전 페이지 필터/정렬 컨벤션·디자인 통일, 지도 상태 필터/정렬 동작
