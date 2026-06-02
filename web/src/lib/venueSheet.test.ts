import { describe, expect, it } from "vitest";
import { venueSummary, sortForSheet, filterByStatus, nextSnap } from "@/lib/venueSheet";
import type { Exhibition } from "@/lib/catalog";

function ex(p: Partial<Exhibition> & { id: string }): Exhibition {
  return {
    id: p.id, source: null, title: p.title ?? p.id, posterImageUrl: null,
    description: null, medium: null, exhibitionType: null, genreTags: [],
    feeType: null, priceMin: null, priceMax: null,
    startDate: p.startDate ?? null, endDate: p.endDate ?? null,
    status: p.status ?? "unknown", openHours: null, venue: null,
    artists: [], sourceUrl: null, featured: false, popularityScore: null,
    lang: null, tr: {},
  };
}

describe("venueSummary", () => {
  it("counts total, ongoing and upcoming", () => {
    const items = [
      ex({ id: "a", status: "ongoing" }),
      ex({ id: "b", status: "ongoing" }),
      ex({ id: "c", status: "upcoming" }),
      ex({ id: "d", status: "past" }),
    ];
    expect(venueSummary(items)).toEqual({ total: 4, ongoing: 2, upcoming: 1 });
  });
});

describe("sortForSheet", () => {
  const items = [
    ex({ id: "past", status: "past", startDate: "2026-01-01", endDate: "2026-02-01" }),
    ex({ id: "soon", status: "ongoing", startDate: "2026-05-01", endDate: "2026-06-05" }),
    ex({ id: "later", status: "ongoing", startDate: "2026-05-20", endDate: "2026-07-01" }),
    ex({ id: "up", status: "upcoming", startDate: "2026-08-01", endDate: "2026-09-01" }),
  ];

  it("closing mode orders ongoing by soonest endDate first", () => {
    const ids = sortForSheet(items, "closing").map((e) => e.id);
    expect(ids[0]).toBe("soon");
    expect(ids[1]).toBe("later");
  });

  it("recent mode orders by latest startDate first", () => {
    const ids = sortForSheet(items, "recent").map((e) => e.id);
    expect(ids[0]).toBe("up");
    expect(ids[ids.length - 1]).toBe("past");
  });

  it("does not mutate the input array", () => {
    const copy = [...items];
    sortForSheet(items, "recent");
    expect(items.map((e) => e.id)).toEqual(copy.map((e) => e.id));
  });
});

describe("filterByStatus", () => {
  const items = [
    ex({ id: "past", status: "past" }),
    ex({ id: "soon", status: "ongoing" }),
    ex({ id: "later", status: "ongoing" }),
    ex({ id: "up", status: "upcoming" }),
  ];

  it("returns everything when no status is selected", () => {
    expect(filterByStatus(items, []).map((e) => e.id)).toEqual(["past", "soon", "later", "up"]);
  });

  it("keeps only ongoing when ongoing is selected", () => {
    expect(filterByStatus(items, ["ongoing"]).map((e) => e.id)).toEqual(["soon", "later"]);
  });

  it("keeps ongoing and upcoming when both are selected (hides ended)", () => {
    expect(filterByStatus(items, ["ongoing", "upcoming"]).map((e) => e.id)).toEqual(["soon", "later", "up"]);
  });

  it("does not mutate the input array", () => {
    const copy = [...items];
    filterByStatus(items, ["ongoing"]);
    expect(items.map((e) => e.id)).toEqual(copy.map((e) => e.id));
  });
});

describe("nextSnap", () => {
  it("drag up always returns full", () => {
    expect(nextSnap("full", -100)).toBe("full");
    expect(nextSnap("peek", -100)).toBe("full");
  });
  it("drag down steps full -> peek -> closed", () => {
    expect(nextSnap("full", 100)).toBe("peek");
    expect(nextSnap("peek", 100)).toBe("closed");
  });
  it("small movement keeps the current snap", () => {
    expect(nextSnap("full", 10)).toBe("full");
    expect(nextSnap("peek", -10)).toBe("peek");
  });
});
