import type { Exhibition, Status } from "@/lib/catalog";
import { regionBucket } from "@/lib/regions";

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
      // f.regions holds coarse city buckets ("서울", "도쿄", …), not raw venue
      // regions, so collapse the venue's granular region before matching.
      const bucket = regionBucket(e.venue?.region);
      if (!bucket || !f.regions.includes(bucket.city)) return false;
    }
    return true;
  });
}

export function searchExhibitions(list: Exhibition[], q: string): Exhibition[] {
  const query = q.trim().toLowerCase();
  if (!query) return list;
  return list.filter((e) => {
    const hay = [
      e.title, e.venue?.name ?? "",
      ...e.artists.map((a) => a.name), ...e.genreTags,
    ].join(" ").toLowerCase();
    return hay.includes(query);
  });
}
