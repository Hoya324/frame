import { describe, expect, it } from "vitest";
import { applyFilters, searchExhibitions, type FilterState } from "@/lib/filters";
import type { Exhibition } from "@/lib/catalog";

function ex(p: Partial<Exhibition>): Exhibition {
  return {
    id: "x", title: "T", titleEn: null, posterImageUrl: null, description: null,
    medium: "photo", exhibitionType: "solo", genreTags: [], feeType: "free",
    priceMin: null, priceMax: null, startDate: "2026-05-01", endDate: "2026-06-30",
    status: "ongoing", openHours: null, venue: null, artists: [],
    sourceUrl: null, featured: false, popularityScore: null, ...p,
  };
}
const EMPTY: FilterState = { statuses: [], mediums: [], types: [], freeOnly: false, regions: [] };

describe("applyFilters", () => {
  it("filters by status", () => {
    const out = applyFilters([ex({ id: "a", status: "ongoing" }), ex({ id: "b", status: "upcoming" })],
      { ...EMPTY, statuses: ["ongoing"] });
    expect(out.map((e) => e.id)).toEqual(["a"]);
  });
  it("filters freeOnly", () => {
    const out = applyFilters([ex({ id: "a", feeType: "free" }), ex({ id: "b", feeType: "paid" })],
      { ...EMPTY, freeOnly: true });
    expect(out.map((e) => e.id)).toEqual(["a"]);
  });
  it("empty filters returns all", () => {
    expect(applyFilters([ex({ id: "a" }), ex({ id: "b" })], EMPTY)).toHaveLength(2);
  });
  it("filters by region from venue", () => {
    const out = applyFilters(
      [ex({ id: "a", venue: { id: "v", name: "n", region: "서울", district: "삼청", lat: null, lng: null } }),
       ex({ id: "b", venue: { id: "v2", name: "n", region: "부산", district: null, lat: null, lng: null } })],
      { ...EMPTY, regions: ["서울"] });
    expect(out.map((e) => e.id)).toEqual(["a"]);
  });
});

describe("searchExhibitions", () => {
  it("matches title, artist, venue (case-insensitive)", () => {
    const list = [
      ex({ id: "a", title: "도시의 표면" }),
      ex({ id: "b", artists: [{ id: "1", name: "Kim Test" }] }),
      ex({ id: "c", venue: { id: "v", name: "류가헌", region: null, district: null, lat: null, lng: null } }),
    ];
    expect(searchExhibitions(list, "도시").map((e) => e.id)).toEqual(["a"]);
    expect(searchExhibitions(list, "kim").map((e) => e.id)).toEqual(["b"]);
    expect(searchExhibitions(list, "류가헌").map((e) => e.id)).toEqual(["c"]);
    expect(searchExhibitions(list, "").map((e) => e.id)).toEqual(["a", "b", "c"]);
  });
});
