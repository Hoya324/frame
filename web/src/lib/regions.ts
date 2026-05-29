import type { Exhibition } from "@/lib/catalog";

export function groupByRegion(list: Exhibition[]): Map<string, Exhibition[]> {
  const groups = new Map<string, Exhibition[]>();
  for (const e of list) {
    const region = e.venue?.region;
    if (!region || e.venue?.lat == null || e.venue?.lng == null) continue;
    const bucket = groups.get(region) ?? [];
    bucket.push(e);
    groups.set(region, bucket);
  }
  return groups;
}
