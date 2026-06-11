import { describe, expect, it } from "vitest";
import { applyFilters, searchExhibitions, type FilterState } from "@/lib/filters";
import type { Exhibition } from "@/lib/catalog";

function ex(p: Partial<Exhibition>): Exhibition {
  return {
    id: "x", source: null, title: "T", posterImageUrl: null, description: null,
    medium: "photo", exhibitionType: "solo", genreTags: [], feeType: "free",
    priceMin: null, priceMax: null, startDate: "2026-05-01", endDate: "2026-06-30",
    status: "ongoing", openHours: null, venue: null, artists: [],
    sourceUrl: null, featured: false, popularityScore: null, lang: null, tr: {}, ...p,
  };
}
const EMPTY: FilterState = { statuses: [], mediums: [], types: [], freeOnly: false, regions: [] };
// Default filter applied on all browse/search/map/scrap pages at initial load.
const DEFAULT_STATUSES: FilterState = { ...EMPTY, statuses: ["ongoing", "upcoming"] };

describe("default status filter (ongoing + upcoming)", () => {
  it("shows ongoing and upcoming, hides past", () => {
    const list = [
      ex({ id: "a", status: "ongoing" }),
      ex({ id: "b", status: "upcoming" }),
      ex({ id: "c", status: "past" }),
    ];
    const out = applyFilters(list, DEFAULT_STATUSES);
    expect(out.map((e) => e.id)).toEqual(["a", "b"]);
  });
  it("all statuses present when filter is empty (legacy no-filter fallback)", () => {
    const list = [
      ex({ id: "a", status: "ongoing" }),
      ex({ id: "b", status: "past" }),
    ];
    expect(applyFilters(list, EMPTY)).toHaveLength(2);
  });
});

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
      [ex({ id: "a", venue: { id: "v", name: "n", region: "서울", district: "삼청", lat: null, lng: null, lang: null, tr: {} } }),
       ex({ id: "b", venue: { id: "v2", name: "n", region: "부산", district: null, lat: null, lng: null, lang: null, tr: {} } })],
      { ...EMPTY, regions: ["서울"] });
    expect(out.map((e) => e.id)).toEqual(["a"]);
  });
});

describe("searchExhibitions", () => {
  it("matches title, artist, venue (case-insensitive)", () => {
    const list = [
      ex({ id: "a", title: "도시의 표면" }),
      ex({ id: "b", artists: [{ id: "1", name: "Kim Test", lang: null, tr: {} }] }),
      ex({ id: "c", venue: { id: "v", name: "류가헌", region: null, district: null, lat: null, lng: null, lang: null, tr: {} } }),
    ];
    expect(searchExhibitions(list, "도시").map((e) => e.id)).toEqual(["a"]);
    expect(searchExhibitions(list, "kim").map((e) => e.id)).toEqual(["b"]);
    expect(searchExhibitions(list, "류가헌").map((e) => e.id)).toEqual(["c"]);
    expect(searchExhibitions(list, "").map((e) => e.id)).toEqual(["a", "b", "c"]);
  });
});
