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
