# 공간 시트(Venue Sheet) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 같은 장소의 여러 전시를 누르면 "하나의 공간 = 여러 전시"를 명확히 보여주고 둘러보기 좋은 반응형 시트(모바일 바텀시트 / 데스크탑 우측 패널)를 띄운다.

**Architecture:** 정렬·요약·스냅 판정 같은 순수 로직은 `lib/venueSheet.ts`로 분리해 vitest로 TDD한다. UI는 신규 `VenueSheet.tsx`(반응형 오버레이)가 맡고, `map/page.tsx`가 선택된 venue 상태를 들고 해당 venue의 전시를 넘긴다. 지도 마커는 `count > 1`일 때 stacked 룩과 선택 강조를 더한다.

**Tech Stack:** Next.js 16, React 19, Tailwind v4, MapLibre GL, vitest + @testing-library/react (jsdom).

> ⚠️ `web/AGENTS.md`: 이 저장소의 Next.js는 학습 데이터와 다를 수 있다. Next 특화 코드를 쓰기 전 `node_modules/next/dist/docs/`의 관련 문서를 확인하라. 본 플랜은 대부분 클라이언트 컴포넌트/순수 함수라 Next 특화 API는 새로 쓰지 않는다.

모든 경로는 저장소 루트 `/Users/hoyana/Desktop/01_sideproject/photo-exhibition-crawler/` 기준. 작업 디렉터리는 `web/`. 테스트는 `cd web && npx vitest run <경로>`로 실행.

---

## Task 1: 순수 헬퍼 `lib/venueSheet.ts` (요약 / 정렬 / 스냅 판정)

**Files:**
- Create: `web/src/lib/venueSheet.ts`
- Test: `web/src/lib/venueSheet.test.ts`

- [ ] **Step 1: 실패하는 테스트 작성**

Create `web/src/lib/venueSheet.test.ts`:

```ts
import { describe, expect, it } from "vitest";
import { venueSummary, sortForSheet, nextSnap } from "@/lib/venueSheet";
import type { Exhibition } from "@/lib/catalog";

function ex(p: Partial<Exhibition> & { id: string }): Exhibition {
  return {
    id: p.id, source: null, title: p.title ?? p.id, posterImageUrl: null,
    description: null, medium: null, exhibitionType: null, genreTags: [],
    feeType: null, priceMin: null, priceMax: null,
    startDate: p.startDate ?? null, endDate: p.endDate ?? null,
    status: p.status ?? "unknown", openHours: null, venue: null,
    artists: [], sourceUrl: null, featured: false, popularityScore: null,
    lang: null, tr: {},
  };
}

describe("venueSummary", () => {
  it("counts total, ongoing and upcoming", () => {
    const items = [
      ex({ id: "a", status: "ongoing" }),
      ex({ id: "b", status: "ongoing" }),
      ex({ id: "c", status: "upcoming" }),
      ex({ id: "d", status: "past" }),
    ];
    expect(venueSummary(items)).toEqual({ total: 4, ongoing: 2, upcoming: 1 });
  });
});

describe("sortForSheet", () => {
  const items = [
    ex({ id: "past", status: "past", startDate: "2026-01-01", endDate: "2026-02-01" }),
    ex({ id: "soon", status: "ongoing", startDate: "2026-05-01", endDate: "2026-06-05" }),
    ex({ id: "later", status: "ongoing", startDate: "2026-05-20", endDate: "2026-07-01" }),
    ex({ id: "up", status: "upcoming", startDate: "2026-08-01", endDate: "2026-09-01" }),
  ];

  it("ongoing mode puts ongoing first, then upcoming, then past", () => {
    const ids = sortForSheet(items, "ongoing").map((e) => e.id);
    expect(ids.slice(0, 2).sort()).toEqual(["later", "soon"]); // 둘 다 ongoing
    expect(ids[2]).toBe("up");
    expect(ids[3]).toBe("past");
  });

  it("closing mode orders ongoing by soonest endDate first", () => {
    const ids = sortForSheet(items, "closing").map((e) => e.id);
    expect(ids[0]).toBe("soon");
    expect(ids[1]).toBe("later");
  });

  it("recent mode orders by latest startDate first", () => {
    const ids = sortForSheet(items, "recent").map((e) => e.id);
    expect(ids[0]).toBe("up"); // 2026-08-01
    expect(ids[ids.length - 1]).toBe("past"); // 2026-01-01
  });

  it("does not mutate the input array", () => {
    const copy = [...items];
    sortForSheet(items, "recent");
    expect(items.map((e) => e.id)).toEqual(copy.map((e) => e.id));
  });
});

describe("nextSnap", () => {
  it("drag up always returns full", () => {
    expect(nextSnap("full", -100)).toBe("full");
    expect(nextSnap("peek", -100)).toBe("full");
  });
  it("drag down steps full -> peek -> closed", () => {
    expect(nextSnap("full", 100)).toBe("peek");
    expect(nextSnap("peek", 100)).toBe("closed");
  });
  it("small movement keeps the current snap", () => {
    expect(nextSnap("full", 10)).toBe("full");
    expect(nextSnap("peek", -10)).toBe("peek");
  });
});
```

- [ ] **Step 2: 테스트 실행 → 실패 확인**

Run: `cd web && npx vitest run src/lib/venueSheet.test.ts`
Expected: FAIL — `venueSheet` 모듈/함수 미정의.

- [ ] **Step 3: 최소 구현 작성**

Create `web/src/lib/venueSheet.ts`:

```ts
import type { Exhibition, Status } from "@/lib/catalog";

export type SortMode = "ongoing" | "closing" | "recent";

export interface VenueSummary {
  total: number;
  ongoing: number;
  upcoming: number;
}

export function venueSummary(items: Exhibition[]): VenueSummary {
  let ongoing = 0;
  let upcoming = 0;
  for (const e of items) {
    if (e.status === "ongoing") ongoing++;
    else if (e.status === "upcoming") upcoming++;
  }
  return { total: items.length, ongoing, upcoming };
}

// 진행중 → 예정 → 정보없음 → 종료 순으로 노출.
const STATUS_RANK: Record<Status, number> = { ongoing: 0, upcoming: 1, unknown: 2, past: 3 };

// Array.prototype.sort는 최신 엔진에서 안정 정렬이므로 동순위 입력 순서를 보존한다.
export function sortForSheet(items: Exhibition[], mode: SortMode): Exhibition[] {
  const copy = [...items];
  if (mode === "ongoing") {
    copy.sort((a, b) => STATUS_RANK[a.status] - STATUS_RANK[b.status]);
  } else if (mode === "closing") {
    copy.sort((a, b) => {
      const ao = a.status === "ongoing" ? 0 : 1;
      const bo = b.status === "ongoing" ? 0 : 1;
      if (ao !== bo) return ao - bo;
      return (a.endDate ?? "9999-99-99").localeCompare(b.endDate ?? "9999-99-99");
    });
  } else {
    // recent
    copy.sort((a, b) => (b.startDate ?? "").localeCompare(a.startDate ?? ""));
  }
  return copy;
}

// 모바일 바텀시트 드래그 종료 시 다음 스냅 위치 판정.
// deltaY > 0 = 아래로 드래그(닫는 방향), < 0 = 위로 드래그(여는 방향).
export function nextSnap(current: "full" | "peek", deltaY: number): "full" | "peek" | "closed" {
  const THRESHOLD = 60;
  if (deltaY < -THRESHOLD) return "full";
  if (deltaY > THRESHOLD) return current === "full" ? "peek" : "closed";
  return current;
}
```

- [ ] **Step 4: 테스트 실행 → 통과 확인**

Run: `cd web && npx vitest run src/lib/venueSheet.test.ts`
Expected: PASS (모든 케이스 green).

- [ ] **Step 5: 커밋**

```bash
git add web/src/lib/venueSheet.ts web/src/lib/venueSheet.test.ts
git commit -m "feat(web): venue sheet pure helpers (summary, sort, snap)"
```

---

## Task 2: i18n 문자열 추가 (ko / en / ja)

**Files:**
- Modify: `web/src/lib/i18n.ts` (ko 블록 `"map.showing"` 다음 ≈L114, en ≈L223, ja ≈L332)

- [ ] **Step 1: ko 블록에 키 추가**

`web/src/lib/i18n.ts`에서 한국어 블록의 `"map.showing": "이 화면의 전시",` 줄 **바로 다음**에 추가:

```ts
  "venue.exhibitions": "전시",
  "venue.close": "닫기",
  "venue.sortOngoing": "진행중 먼저",
  "venue.sortClosing": "마감임박",
  "venue.sortRecent": "최신순",
```

- [ ] **Step 2: en 블록에 키 추가**

영어 블록의 `"map.showing": "In view",` 줄 **바로 다음**에 추가:

```ts
  "venue.exhibitions": "Exhibitions",
  "venue.close": "Close",
  "venue.sortOngoing": "Now showing",
  "venue.sortClosing": "Closing soon",
  "venue.sortRecent": "Newest",
```

- [ ] **Step 3: ja 블록에 키 추가**

일본어 블록의 `"map.showing": "表示中の展示",` 줄 **바로 다음**에 추가:

```ts
  "venue.exhibitions": "展示",
  "venue.close": "閉じる",
  "venue.sortOngoing": "開催中を先に",
  "venue.sortClosing": "終了間近",
  "venue.sortRecent": "新着順",
```

- [ ] **Step 4: 타입/린트 확인**

Run: `cd web && npx tsc --noEmit && npx eslint src/lib/i18n.ts`
Expected: 에러 없음.

- [ ] **Step 5: 커밋**

```bash
git add web/src/lib/i18n.ts
git commit -m "feat(web): i18n strings for venue sheet"
```

---

## Task 3: `VenueSheet.tsx` 컴포넌트 (반응형 시트 + 정렬 + 그리드)

**Files:**
- Create: `web/src/components/VenueSheet.tsx`
- Test: `web/src/components/VenueSheet.test.tsx`

- [ ] **Step 1: 실패하는 테스트 작성**

Create `web/src/components/VenueSheet.test.tsx` (ExhibitionCard.test.tsx의 provider/mock 패턴을 그대로 따른다):

```tsx
import { screen, fireEvent } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { renderWithLang } from "@/test/lang";

vi.mock("@/components/AuthProvider", () => ({
  useBookmarks: () => ({ ids: new Set<string>(), isScrapped: () => false, toggle: vi.fn() }),
}));

import { VenueSheet } from "@/components/VenueSheet";
import type { Exhibition, VenueEmbed } from "@/lib/catalog";

const VENUE: VenueEmbed = {
  id: "v1", name: "캐논갤러리", region: "부산", district: "해운대구",
  lat: 35.16, lng: 129.16, lang: null, tr: {},
};

function ex(id: string, p: Partial<Exhibition>): Exhibition {
  return {
    id, source: null, title: p.title ?? id, posterImageUrl: null,
    description: null, medium: null, exhibitionType: null, genreTags: [],
    feeType: null, priceMin: null, priceMax: null,
    startDate: p.startDate ?? null, endDate: p.endDate ?? null,
    status: p.status ?? "unknown", openHours: null, venue: VENUE,
    artists: [], sourceUrl: null, featured: false, popularityScore: null,
    lang: null, tr: {},
  };
}

const ITEMS: Exhibition[] = [
  ex("e-past", { title: "지난전시", status: "past", startDate: "2026-01-01", endDate: "2026-02-01" }),
  ex("e-soon", { title: "곧마감", status: "ongoing", startDate: "2026-05-01", endDate: "2026-06-05" }),
  ex("e-later", { title: "여유전시", status: "ongoing", startDate: "2026-05-20", endDate: "2026-07-01" }),
];

describe("VenueSheet", () => {
  // 카드 제목의 DOM 등장 순서를 반환 (ExhibitionCard 제목은 heading이 아니라 div이므로
  // role 대신 텍스트 노드의 문서 위치로 순서를 판정한다).
  function cardTitlesInOrder(): string[] {
    const titles = ["곧마감", "여유전시", "지난전시"];
    return titles
      .map((tt) => ({ tt, node: screen.getByText(tt) }))
      .sort((a, b) =>
        a.node.compareDocumentPosition(b.node) & Node.DOCUMENT_POSITION_FOLLOWING ? -1 : 1,
      )
      .map((p) => p.tt);
  }

  it("renders venue name, location and status summary", () => {
    renderWithLang(<VenueSheet venue={VENUE} exhibitions={ITEMS} onClose={vi.fn()} />);
    expect(screen.getByRole("heading", { name: /캐논갤러리/ })).toBeInTheDocument();
    expect(screen.getByText(/부산 · 해운대구/)).toBeInTheDocument();
    // "전시 3 · 진행중 2" — 텍스트가 <b> 등으로 쪼개지므로 testid로 컨테이너를 잡는다.
    const summary = screen.getByTestId("venue-summary");
    expect(summary.textContent).toContain("3");
    expect(summary.textContent).toContain("진행중 2");
  });

  it("renders one card per exhibition", () => {
    renderWithLang(<VenueSheet venue={VENUE} exhibitions={ITEMS} onClose={vi.fn()} />);
    expect(screen.getByText("곧마감")).toBeInTheDocument();
    expect(screen.getByText("여유전시")).toBeInTheDocument();
    expect(screen.getByText("지난전시")).toBeInTheDocument();
  });

  it("default ongoing sort lists ongoing exhibitions before past", () => {
    renderWithLang(<VenueSheet venue={VENUE} exhibitions={ITEMS} onClose={vi.fn()} />);
    expect(cardTitlesInOrder()[2]).toBe("지난전시");
  });

  it("switching to '마감임박' puts the soonest-closing ongoing first", () => {
    renderWithLang(<VenueSheet venue={VENUE} exhibitions={ITEMS} onClose={vi.fn()} />);
    fireEvent.click(screen.getByRole("button", { name: "마감임박" }));
    expect(cardTitlesInOrder()[0]).toBe("곧마감");
  });

  it("calls onClose when the backdrop is clicked", () => {
    const onClose = vi.fn();
    renderWithLang(<VenueSheet venue={VENUE} exhibitions={ITEMS} onClose={onClose} />);
    fireEvent.click(screen.getAllByRole("button", { name: "닫기" })[0]);
    expect(onClose).toHaveBeenCalled();
  });
});
```

- [ ] **Step 2: 테스트 실행 → 실패 확인**

Run: `cd web && npx vitest run src/components/VenueSheet.test.tsx`
Expected: FAIL — `VenueSheet` 모듈 미존재.

- [ ] **Step 3: 컴포넌트 구현**

Create `web/src/components/VenueSheet.tsx`:

```tsx
"use client";
import { useEffect, useState } from "react";
import { X } from "lucide-react";
import { ExhibitionCard } from "@/components/ExhibitionCard";
import { TranslatableText } from "@/components/TranslatableText";
import { useLang } from "@/components/LanguageProvider";
import { venueSummary, sortForSheet, nextSnap, type SortMode } from "@/lib/venueSheet";
import type { Exhibition, VenueEmbed } from "@/lib/catalog";

const SORTS: { mode: SortMode; key: string }[] = [
  { mode: "ongoing", key: "venue.sortOngoing" },
  { mode: "closing", key: "venue.sortClosing" },
  { mode: "recent", key: "venue.sortRecent" },
];

export function VenueSheet({
  venue, exhibitions, onClose,
}: {
  venue: VenueEmbed;
  exhibitions: Exhibition[];
  onClose: () => void;
}) {
  const { t } = useLang();
  const [sort, setSort] = useState<SortMode>("ongoing");
  const [snap, setSnap] = useState<"full" | "peek">("full");
  const [dragY, setDragY] = useState(0);
  const [startY, setStartY] = useState<number | null>(null);

  // 다른 venue가 열리면 시트를 처음 상태로 리셋.
  useEffect(() => {
    setSort("ongoing");
    setSnap("full");
    setDragY(0);
    setStartY(null);
  }, [venue.id]);

  // Esc로 닫기.
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => { if (e.key === "Escape") onClose(); };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [onClose]);

  const summary = venueSummary(exhibitions);
  const sorted = sortForSheet(exhibitions, sort);

  const onPointerDown = (e: React.PointerEvent) => {
    setStartY(e.clientY);
    (e.currentTarget as HTMLElement).setPointerCapture(e.pointerId);
  };
  const onPointerMove = (e: React.PointerEvent) => {
    if (startY === null) return;
    setDragY(Math.max(0, e.clientY - startY));
  };
  const onPointerUp = (e: React.PointerEvent) => {
    if (startY === null) return;
    const target = nextSnap(snap, e.clientY - startY);
    setStartY(null);
    setDragY(0);
    if (target === "closed") onClose();
    else setSnap(target);
  };

  const basePct = snap === "full" ? 0 : 45;

  return (
    <div className="fixed inset-0 z-[60]" role="dialog" aria-modal="true">
      <button
        type="button"
        aria-label={t("venue.close")}
        onClick={onClose}
        className="absolute inset-0 bg-black/50 md:bg-black/30"
      />
      <div
        className="absolute inset-x-0 bottom-0 flex max-h-[88vh] flex-col rounded-t-2xl border border-line bg-bg shadow-[0_-8px_40px_rgba(0,0,0,0.6)] transition-transform duration-200 md:inset-y-0 md:left-auto md:right-0 md:max-h-none md:w-[400px] md:rounded-none md:border-l md:!translate-y-0"
        style={{ transform: `translateY(calc(${basePct}% + ${dragY}px))` }}
      >
        {/* 모바일 드래그 핸들 */}
        <div
          className="flex shrink-0 cursor-grab touch-none justify-center py-2.5 md:hidden"
          onPointerDown={onPointerDown}
          onPointerMove={onPointerMove}
          onPointerUp={onPointerUp}
        >
          <span className="h-1.5 w-10 rounded-full bg-line2" />
        </div>

        {/* 헤더 */}
        <div className="shrink-0 border-b border-line px-5 pb-3 pt-1 md:pt-5">
          <div className="flex items-start gap-3">
            <div className="min-w-0 flex-1">
              <h2 className="truncate text-[18px] font-bold leading-tight">
                <TranslatableText original={venue.name} tr={venue.tr} field="name" />
              </h2>
              <div className="mt-1 text-[12.5px] text-tx2">
                {[venue.region, venue.district].filter(Boolean).join(" · ")}
              </div>
              <div data-testid="venue-summary" className="mt-1.5 text-[12px] text-tx3">
                {t("venue.exhibitions")} <b className="text-tx">{summary.total}</b>
                {summary.ongoing > 0 ? ` · ${t("filter.ongoing")} ${summary.ongoing}` : ""}
                {summary.upcoming > 0 ? ` · ${t("filter.upcoming")} ${summary.upcoming}` : ""}
              </div>
            </div>
            <button
              type="button"
              onClick={onClose}
              aria-label={t("venue.close")}
              className="hidden rounded-full p-1.5 text-tx2 transition hover:bg-line md:block"
            >
              <X size={18} />
            </button>
          </div>

          {/* 정렬 칩 */}
          <div className="mt-3 flex gap-2">
            {SORTS.map((s) => (
              <button
                key={s.mode}
                type="button"
                onClick={() => setSort(s.mode)}
                aria-pressed={sort === s.mode}
                className={`rounded-full px-3 py-1 text-xs font-semibold transition ${
                  sort === s.mode ? "bg-white text-black" : "border border-line2 text-tx2"
                }`}
              >
                {t(s.key)}
              </button>
            ))}
          </div>
        </div>

        {/* 포스터 2열 그리드 */}
        <div className="grid grid-cols-2 gap-4 overflow-y-auto p-5">
          {sorted.map((e) => (
            <ExhibitionCard key={e.id} exhibition={e} />
          ))}
        </div>
      </div>
    </div>
  );
}
```

- [ ] **Step 4: 테스트 실행 → 통과 확인**

Run: `cd web && npx vitest run src/components/VenueSheet.test.tsx`
Expected: PASS. (summary는 `data-testid="venue-summary"`로 조회하므로 텍스트 분할 문제 없음.)

- [ ] **Step 5: 커밋**

```bash
git add web/src/components/VenueSheet.tsx web/src/components/VenueSheet.test.tsx
git commit -m "feat(web): VenueSheet responsive bottom-sheet/panel with sort"
```

---

## Task 4: `map/page.tsx` 배선 — 사이드바 필터를 시트로 대체

**Files:**
- Modify: `web/src/app/map/page.tsx`

기존: 멀티 전시 venue 클릭 → `venue` state로 사이드바 필터. 변경: `sheetVenueId` state로 `VenueSheet`를 띄운다. 사이드바(우측 360px 목록)는 in-view 목록 그대로 유지.

- [ ] **Step 1: import + 상태 교체**

`web/src/app/map/page.tsx` 상단 import에 추가:

```tsx
import { VenueSheet } from "@/components/VenueSheet";
```

`const [venue, setVenue] = useState<{ id: string; name: string } | null>(null);` 줄을 다음으로 교체:

```tsx
  const [sheetVenueId, setSheetVenueId] = useState<string | null>(null);
```

- [ ] **Step 2: `toggle`에서 venue 리셋 제거**

기존:

```tsx
  const toggle = (v: string) => {
    setVenue(null);
    setCities((c) => (c.includes(v) ? c.filter((x) => x !== v) : [...c, v]));
  };
```

교체:

```tsx
  const toggle = (v: string) => {
    setCities((c) => (c.includes(v) ? c.filter((x) => x !== v) : [...c, v]));
  };
```

- [ ] **Step 3: `listed`에서 venue 필터 분기 제거**

기존 `listed` 메모 내부의 `base` 정의:

```tsx
    const base = venue
      ? items.filter((e) => e.venue?.id === venue.id)
      : visibleIds
        ? items.filter((e) => visibleIds.has(e.id))
        : items;
```

교체:

```tsx
    const base = visibleIds ? items.filter((e) => visibleIds.has(e.id)) : items;
```

그리고 `listed` 메모의 의존성 배열에서 `venue`를 제거: `}, [items, venue, visibleIds, userLoc]);` → `}, [items, visibleIds, userLoc]);`

- [ ] **Step 4: 선택된 venue의 메타/전시 목록 계산**

`listed` 메모 아래에 추가:

```tsx
  const sheet = useMemo(() => {
    if (!sheetVenueId) return null;
    const exhibitions = items.filter((e) => e.venue?.id === sheetVenueId);
    const venueMeta = exhibitions[0]?.venue ?? null;
    if (!venueMeta) return null;
    return { venue: venueMeta, exhibitions };
  }, [items, sheetVenueId]);
```

- [ ] **Step 5: venue 필터 칩 제거**

기존 JSX의 venue 칩 블록 전체 삭제:

```tsx
        {venue && (
          <button
            type="button"
            onClick={() => setVenue(null)}
            className="flex items-center gap-1.5 rounded-full bg-white px-3 py-1 text-xs font-semibold text-black transition active:scale-95"
          >
            {venue.name}
            <X size={13} />
          </button>
        )}
```

이로 인해 `X` import가 더 이상 쓰이지 않으면 `lucide-react` import에서 `X` 제거: `import { MapPin, Loader2 } from "lucide-react";`

- [ ] **Step 6: MapView 콜백 + 시트 렌더링 연결**

`MapView`의 `onVenueSelect`를 교체하고 `selectedVenueId` prop 추가:

```tsx
        <MapView
          items={items}
          height={560}
          userLocation={userLoc}
          selectedVenueId={sheetVenueId}
          onViewChange={(ids) => setVisibleIds(new Set(ids))}
          onVenueSelect={(id) => setSheetVenueId(id)}
          onSelect={(id) => router.push(`/exhibitions/${id}`)}
        />
```

그리고 `</main>` 닫기 직전에 시트 렌더링 추가:

```tsx
      {sheet && (
        <VenueSheet
          venue={sheet.venue}
          exhibitions={sheet.exhibitions}
          onClose={() => setSheetVenueId(null)}
        />
      )}
```

- [ ] **Step 7: 타입/린트/빌드 확인**

Run: `cd web && npx tsc --noEmit && npx eslint src/app/map/page.tsx`
Expected: 에러 없음. (`onVenueSelect`가 이제 `(id) => ...` 1-인자로 호출됨 — Task 5에서 `MapView` 시그니처를 `(venueId: string)`로 맞춘다. 이 단계에서 타입 에러가 나면 Task 5 적용 후 재확인.)

- [ ] **Step 8: 커밋**

```bash
git add web/src/app/map/page.tsx
git commit -m "feat(web): open VenueSheet on multi-exhibition venue tap"
```

---

## Task 5: `MapView` stacked 마커 + 선택 강조 + CSS

**Files:**
- Modify: `web/src/components/MapView.tsx`
- Modify: `web/src/app/globals.css`

- [ ] **Step 1: stacked 마커 CSS 추가**

`web/src/app/globals.css`의 `.frame-marker-badge { ... }` 규칙(끝 `}` 다음, ≈L105) 바로 뒤에 추가:

```css
/* 여러 전시를 여는 venue: 뒤에 카드가 겹쳐 쌓인 모양으로 "한 공간 다수 전시"를 암시 */
.frame-poster-marker--stacked::before,
.frame-poster-marker--stacked::after {
  content: "";
  position: absolute;
  inset: 0;
  border-radius: 6px;
  border: 2px solid #fff;
  background: #2a2a2a;
  z-index: -1;
}
.frame-poster-marker--stacked::before {
  transform: translate(3px, 4px) rotate(4deg);
}
.frame-poster-marker--stacked::after {
  transform: translate(6px, 7px) rotate(7deg);
}

/* 시트로 선택된 마커 강조 */
.frame-poster-marker--selected {
  transform: scale(1.18);
  border-color: #fbbf24;
  box-shadow: 0 0 0 3px rgba(251, 191, 36, 0.5), 0 2px 8px rgba(0, 0, 0, 0.55);
  z-index: 2;
}
.frame-poster-marker--selected:hover {
  transform: scale(1.18);
}
```

- [ ] **Step 2: `posterMarkerEl`에 stacked 클래스 부여**

`web/src/components/MapView.tsx`의 `posterMarkerEl` 함수에서 count 배지 블록을 다음으로 교체:

기존:

```tsx
  const count = Number(p.count ?? 1);
  if (count > 1) {
    const badge = document.createElement("span");
    badge.className = "frame-marker-badge";
    badge.textContent = count > 99 ? "99+" : String(count);
    el.appendChild(badge);
  }
```

교체:

```tsx
  const count = Number(p.count ?? 1);
  if (count > 1) {
    el.classList.add("frame-poster-marker--stacked");
    const badge = document.createElement("span");
    badge.className = "frame-marker-badge";
    badge.textContent = count > 99 ? "99+" : String(count);
    el.appendChild(badge);
  }
```

- [ ] **Step 3: prop 시그니처 변경 — `onVenueSelect`를 1-인자로, `selectedVenueId` 추가**

`MapView`의 props 타입과 구조분해를 수정.

기존:

```tsx
export function MapView({ items, height = 480, onSelect, onVenueSelect, onViewChange, userLocation }: {
  items: Exhibition[];
  height?: number;
  onSelect?: (id: string) => void;
  onVenueSelect?: (venueId: string, venueName: string) => void;
  onViewChange?: (visibleIds: string[]) => void;
  userLocation?: [number, number] | null;
}) {
```

교체:

```tsx
export function MapView({ items, height = 480, onSelect, onVenueSelect, onViewChange, userLocation, selectedVenueId }: {
  items: Exhibition[];
  height?: number;
  onSelect?: (id: string) => void;
  onVenueSelect?: (venueId: string) => void;
  onViewChange?: (visibleIds: string[]) => void;
  userLocation?: [number, number] | null;
  selectedVenueId?: string | null;
}) {
```

- [ ] **Step 4: marker 엘리먼트를 ref에 보관 + 클릭 콜백 1-인자화**

`const mapRef = useRef<maplibregl.Map | null>(null);` 다음 줄에 ref 추가:

```tsx
  const markerEls = useRef<Record<string, HTMLElement>>({});
  const selectedVenueRef = useRef<string | null>(selectedVenueId ?? null);
  useEffect(() => { selectedVenueRef.current = selectedVenueId ?? null; }, [selectedVenueId]);
```

`syncMarkers` 내부에서 마커 생성 블록을 수정해 (a) 엘리먼트를 ref에 저장, (b) 멀티 venue 클릭을 1-인자로 호출, (c) 생성 시점에 현재 선택 상태 반영.

기존:

```tsx
        let marker = markers[venueId];
        if (!marker) {
          // Single-exhibition venue → open it directly; multi → select the
          // venue so the sidebar lists all of its exhibitions.
          const el = posterMarkerEl(p, () => {
            if (Number(p.count ?? 1) > 1) onVenueSelectRef.current?.(venueId, String(p.venueName ?? ""));
            else onSelectRef.current?.(String(p.firstId));
          });
          marker = markers[venueId] = new maplibregl.Marker({ element: el }).setLngLat(coords);
        }
```

교체:

```tsx
        let marker = markers[venueId];
        if (!marker) {
          // 단일 전시 venue → 바로 상세로; 멀티 → 공간 시트 오픈.
          const el = posterMarkerEl(p, () => {
            if (Number(p.count ?? 1) > 1) onVenueSelectRef.current?.(venueId);
            else onSelectRef.current?.(String(p.firstId));
          });
          if (venueId === selectedVenueRef.current) el.classList.add("frame-poster-marker--selected");
          markerEls.current[venueId] = el;
          marker = markers[venueId] = new maplibregl.Marker({ element: el }).setLngLat(coords);
        }
```

> 참고: `onVenueSelectRef`의 타입도 1-인자가 되도록, 컴포넌트 상단의 `onVenueSelectRef`는 `useRef(onVenueSelect)`라 prop 타입을 따라 자동으로 `(venueId: string) => void`가 된다. 추가 변경 불필요.

- [ ] **Step 5: 선택 강조 토글 effect 추가**

지도 cleanup이 들어있는 메인 effect(`}, [items]);`) **다음**, "내 위치" effect 위에 새 effect 추가:

```tsx
  // 시트로 선택된 venue 마커를 강조 (지도 재생성 없이 클래스만 토글).
  useEffect(() => {
    for (const id in markerEls.current) {
      markerEls.current[id].classList.toggle("frame-poster-marker--selected", id === selectedVenueId);
    }
  }, [selectedVenueId, items]);
```

- [ ] **Step 6: cleanup에서 markerEls 비우기**

메인 effect의 return cleanup을 수정.

기존:

```tsx
    return () => {
      for (const id in markers) markers[id].remove();
      map.remove();
      mapRef.current = null;
    };
```

교체:

```tsx
    return () => {
      for (const id in markers) markers[id].remove();
      markerEls.current = {};
      map.remove();
      mapRef.current = null;
    };
```

- [ ] **Step 7: 타입/린트/빌드 확인**

Run: `cd web && npx tsc --noEmit && npx eslint src/components/MapView.tsx src/app/map/page.tsx`
Expected: 에러 없음 (Task 4의 `onVenueSelect={(id) => ...}` 1-인자 호출과 시그니처 일치).

- [ ] **Step 8: 전체 테스트 + 빌드**

Run: `cd web && npx vitest run && npx next build`
Expected: 모든 테스트 PASS, 빌드 성공.

- [ ] **Step 9: 커밋**

```bash
git add web/src/components/MapView.tsx web/src/app/globals.css
git commit -m "feat(web): stacked markers and selection highlight for venues"
```

---

## Task 6: 수동 검증 (실제 앱)

**Files:** 없음 (실행/관찰만)

- [ ] **Step 1: 개발 서버 실행 후 지도 페이지 열기**

Run: `cd web && npx next dev` → 브라우저 `http://localhost:3000/map`

- [ ] **Step 2: 다음을 눈으로 확인**

- 전시가 여러 개인 venue 마커가 **카드 겹친 stacked 모양 + 개수 배지**로 보인다.
- 단일 전시 venue 마커는 stacked가 아니다.
- 멀티 venue 마커 클릭 시 **시트가 열리고**, 헤더에 공간명·위치·`전시 N · 진행중 X` 요약, 정렬 칩 3종, 포스터 2열 그리드가 보인다.
- 클릭한 마커가 지도에서 **강조(노란 테두리/확대)**된다.
- 정렬 칩 `진행중 먼저 / 마감임박 / 최신순` 전환 시 그리드 순서가 바뀐다.
- 단일 전시 venue 클릭 시 시트 없이 바로 상세로 이동한다.
- 데스크탑: 우측 패널 / 모바일(개발자도구 모바일 뷰): 하단 바텀시트로 뜨고, 핸들을 아래로 끌면 peek→닫힘, 위로 끌면 full, 배경/Esc로 닫힌다.

- [ ] **Step 3: 검증 결과 기록**

문제가 없으면 이 태스크 완료. 회귀가 있으면 superpowers:systematic-debugging로 디버깅.

---

## 완료 기준

- `cd web && npx vitest run` 전부 통과
- `cd web && npx next build` 성공
- 멀티 전시 venue: stacked 마커 → 클릭 → 반응형 시트(정렬/그리드) → 마커 강조
- 단일 전시 venue: 기존대로 바로 상세 이동
