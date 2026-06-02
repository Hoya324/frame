import type { Exhibition } from "@/lib/catalog";

// 정렬(언제나 하나 선택) — 상태 필터와 별개 축이다.
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

// Array.prototype.sort는 최신 엔진에서 안정 정렬이므로 동순위 입력 순서를 보존한다.
export function sortForSheet(items: Exhibition[], mode: SortMode): Exhibition[] {
  const copy = [...items];
  if (mode === "closing") {
    // 아직 진행중인(=관람 가능한) 전시를 마감 임박 순으로 위에, 종료된 건 아래로.
    copy.sort((a, b) => {
      const ao = a.status === "ongoing" ? 0 : 1;
      const bo = b.status === "ongoing" ? 0 : 1;
      if (ao !== bo) return ao - bo;
      return (a.endDate ?? "9999-99-99").localeCompare(b.endDate ?? "9999-99-99");
    });
  } else {
    // recent: 시작일 최신순.
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
