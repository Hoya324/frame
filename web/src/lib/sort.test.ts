import { describe, expect, it } from "vitest";
import { sortExhibitions } from "@/lib/sort";
import type { Exhibition } from "@/lib/catalog";

function ex(p: Partial<Exhibition> & { id: string }): Exhibition {
  return {
    id: p.id, source: null, title: p.id, posterImageUrl: null, description: null,
    medium: null, exhibitionType: null, genreTags: [], feeType: null, priceMin: null, priceMax: null,
    startDate: p.startDate ?? null, endDate: p.endDate ?? null, status: p.status ?? "unknown",
    openHours: null, venue: p.venue ?? null, artists: [], sourceUrl: null,
    featured: p.featured ?? false, popularityScore: p.popularityScore ?? null, lang: null, tr: {},
  };
}
const v = (lng: number, lat: number) => ({ id: "v", name: "v", region: null, district: null, lat, lng, lang: null, tr: {} });

const ITEMS = [
  ex({ id: "past", status: "past", startDate: "2026-01-01", endDate: "2026-02-01", popularityScore: 9 }),
  ex({ id: "soon", status: "ongoing", startDate: "2026-05-01", endDate: "2026-06-05" }),
  ex({ id: "later", status: "ongoing", startDate: "2026-05-20", endDate: "2026-07-01" }),
  ex({ id: "up", status: "upcoming", startDate: "2026-08-01", endDate: "2026-09-01" }),
  ex({ id: "feat", status: "ongoing", startDate: "2026-04-01", endDate: "2026-12-01", featured: true, popularityScore: 1 }),
];

describe("sortExhibitions", () => {
  it("recommended puts featured first, then by popularity", () => {
    const ids = sortExhibitions(ITEMS, "recommended").map((e) => e.id);
    expect(ids[0]).toBe("feat");
  });
  it("closing puts ongoing (soonest end first) before non-ongoing", () => {
    const ids = sortExhibitions(ITEMS, "closing").map((e) => e.id);
    expect(ids.slice(0, 3)).toEqual(["soon", "later", "feat"]); // 진행중을 마감 순으로
    expect(ids.indexOf("past")).toBeGreaterThan(2); // 종료/예정은 진행중 뒤
    expect(ids.indexOf("up")).toBeGreaterThan(2);
  });
  it("recent orders by newest start date", () => {
    const ids = sortExhibitions(ITEMS, "recent").map((e) => e.id);
    expect(ids[0]).toBe("up");
  });
  it("nearby orders by distance from userLoc; falls back to recommended without it", () => {
    const near = ex({ id: "near", status: "ongoing", venue: v(127.0, 37.5) });
    const far = ex({ id: "far", status: "ongoing", venue: v(135.0, 34.0) });
    const ids = sortExhibitions([far, near], "nearby", { userLoc: [127.0, 37.5] }).map((e) => e.id);
    expect(ids[0]).toBe("near");
    expect(() => sortExhibitions([far, near], "nearby")).not.toThrow();
  });
  it("does not mutate input", () => {
    const copy = [...ITEMS];
    sortExhibitions(ITEMS, "recent");
    expect(ITEMS.map((e) => e.id)).toEqual(copy.map((e) => e.id));
  });
});
