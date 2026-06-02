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

// 비파괴 정렬. Array.prototype.sort는 안정 정렬이므로 동순위 입력 순서를 보존한다.
export function sortExhibitions(items: Exhibition[], key: SortKey, ctx: SortContext = {}): Exhibition[] {
  const copy = [...items];
  if (key === "recommended") {
    copy.sort(byRecommended);
  } else if (key === "closing") {
    // 진행중(=관람 가능)을 마감 임박 순으로 위에, 종료된 건 아래로.
    copy.sort((a, b) => {
      const ao = a.status === "ongoing" ? 0 : 1;
      const bo = b.status === "ongoing" ? 0 : 1;
      if (ao !== bo) return ao - bo;
      return (a.endDate ?? "9999-99-99").localeCompare(b.endDate ?? "9999-99-99");
    });
  } else if (key === "recent") {
    copy.sort((a, b) => (b.startDate ?? "").localeCompare(a.startDate ?? ""));
  } else {
    // nearby: userLoc 없으면 recommended로 폴백.
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
