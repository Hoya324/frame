import type { Exhibition } from "@/lib/catalog";
import { sortExhibitions } from "@/lib/sort";

// 정렬(언제나 하나 선택) — 상태 필터와 별개 축이다. 공용 SortKey의 부분집합.
export type SortMode = "closing" | "recent";
// 상태 필터(다중 선택 가능, 비어 있으면 전체).
export type StatusFilter = "ongoing" | "upcoming";

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

// 상태 필터: 선택된 상태만 남긴다. 아무것도 선택하지 않으면 전체를 그대로 반환.
export function filterByStatus(items: Exhibition[], statuses: StatusFilter[]): Exhibition[] {
  if (statuses.length === 0) return items;
  const set = new Set<string>(statuses);
  return items.filter((e) => set.has(e.status));
}

// 공용 정렬 로직에 위임(중복 제거). 공간시트는 closing/recent만 노출.
export function sortForSheet(items: Exhibition[], mode: SortMode): Exhibition[] {
  return sortExhibitions(items, mode);
}

// 모바일 바텀시트 드래그 종료 시 다음 스냅 위치 판정.
// deltaY > 0 = 아래로 드래그(닫는 방향), < 0 = 위로 드래그(여는 방향).
export function nextSnap(current: "full" | "peek", deltaY: number): "full" | "peek" | "closed" {
  const THRESHOLD = 60;
  if (deltaY < -THRESHOLD) return "full";
  if (deltaY > THRESHOLD) return current === "full" ? "peek" : "closed";
  return current;
}
