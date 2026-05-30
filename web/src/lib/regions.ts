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

export type Country = "한국" | "일본";

const KR_REGIONS = new Set([
  "서울", "경기", "인천", "부산", "대구", "광주", "대전", "울산", "세종",
  "강원", "충북", "충남", "전북", "전남", "경북", "경남", "제주",
]);

/** Coarse, user-facing location bucket for a raw venue region.
 *
 * The crawler emits 50+ granular regions — Korean provinces plus dozens of
 * Tokyo ward groupings ("新宿、初台、四ツ谷") and Japanese prefectures. Surfacing
 * them all as filter chips is unusable, so we collapse them to a country and a
 * major-city bucket. Returns null for venues with no region. */
export function regionBucket(
  raw: string | null | undefined,
): { country: Country; city: string } | null {
  if (!raw) return null;
  if (KR_REGIONS.has(raw)) {
    let city = "한국 기타";
    if (raw === "서울") city = "서울";
    else if (raw === "부산") city = "부산";
    else if (raw === "경기" || raw === "인천") city = "경기·인천";
    return { country: "한국", city };
  }
  // Everything else is a Japanese region. Tokyo wards arrive as comma-joined
  // district names ("、") or contain 東京; prefectures end in 県/府/都.
  let city = "일본 기타";
  if (raw.includes("大阪")) city = "오사카";
  else if (raw.includes("京都")) city = "교토";
  else if (raw.includes("東京") || raw.includes("、")) city = "도쿄";
  return { country: "일본", city };
}

/** Ordered city buckets per country, for stable chip rendering. */
export const CITY_ORDER: Record<Country, string[]> = {
  한국: ["서울", "경기·인천", "부산", "한국 기타"],
  일본: ["도쿄", "오사카", "교토", "일본 기타"],
};
