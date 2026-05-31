import { describe, expect, it } from "vitest";
import { groupByRegion } from "@/lib/regions";
import type { Exhibition } from "@/lib/catalog";

function ex(id: string, region: string | null, lat: number | null): Exhibition {
  return {
    id, title: id, posterImageUrl: null, description: null, medium: null,
    exhibitionType: null, genreTags: [], feeType: null, priceMin: null, priceMax: null,
    startDate: null, endDate: null, status: "ongoing", openHours: null,
    venue: region || lat ? { id: "v", name: "v", region, district: null, lat, lng: lat, lang: null, tr: {} } : null,
    artists: [], sourceUrl: null, featured: false, popularityScore: null,
    lang: null, tr: {},
  };
}

describe("groupByRegion", () => {
  it("buckets exhibitions with coords by region, drops those without coords", () => {
    const groups = groupByRegion([ex("a", "서울", 37.5), ex("b", "서울", 37.6), ex("c", "부산", 35.1), ex("d", null, null)]);
    expect(groups.get("서울")?.length).toBe(2);
    expect(groups.get("부산")?.length).toBe(1);
    expect([...groups.keys()]).not.toContain(null);
  });
});
