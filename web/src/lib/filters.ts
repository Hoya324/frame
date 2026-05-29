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
