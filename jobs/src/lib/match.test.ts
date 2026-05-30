import { describe, expect, it } from "vitest";
import { closingSoonForReminder, matchCustom } from "./match";
import type { JobExhibition } from "./catalog";

function ex(p: Partial<JobExhibition>): JobExhibition {
  return {
    id: "x", title: "T", medium: "photo", exhibitionType: "solo", genreTags: [],
    feeType: "free", startDate: "2026-05-01", endDate: "2026-06-30", status: "ongoing",
    posterImageUrl: null, sourceUrl: null, venueName: "V", region: "서울", artistNames: [], ...p,
  };
}
const TODAY = new Date("2026-05-30T00:00:00+09:00");

describe("closingSoonForReminder", () => {
  it("returns exhibitions ending in exactly 3 or 1 days", () => {
    const list = [
      ex({ id: "d3", endDate: "2026-06-02" }), // D-3
      ex({ id: "d1", endDate: "2026-05-31" }), // D-1
      ex({ id: "d2", endDate: "2026-06-01" }), // D-2 (excluded)
      ex({ id: "d0", endDate: "2026-05-30" }), // D-day (excluded)
    ];
    const out = closingSoonForReminder(list, TODAY);
    expect(out.map((e) => e.id).sort()).toEqual(["d1", "d3"]);
  });
});

describe("matchCustom", () => {
  it("matches by region OR medium across set dimensions (AND across dimensions)", () => {
    const list = [
      ex({ id: "a", region: "서울", medium: "photo" }),
      ex({ id: "b", region: "부산", medium: "photo" }),
      ex({ id: "c", region: "서울", medium: "video" }),
    ];
    // region in [서울] AND medium in [photo]
    expect(matchCustom(list, { regions: ["서울"], mediums: ["photo"] }).map((e) => e.id)).toEqual(["a"]);
    // only region constraint
    expect(matchCustom(list, { regions: ["서울"] }).map((e) => e.id)).toEqual(["a", "c"]);
  });
  it("returns [] when no filters are set", () => {
    expect(matchCustom([ex({})], {})).toEqual([]);
    expect(matchCustom([ex({})], { regions: [], mediums: [] })).toEqual([]);
  });
  it("matches by artist and genre", () => {
    const list = [
      ex({ id: "a", artistNames: ["김작가"] }),
      ex({ id: "b", genreTags: ["다큐"] }),
      ex({ id: "c", artistNames: ["다른작가"] }),
    ];
    expect(matchCustom(list, { artists: ["김작가"] }).map((e) => e.id)).toEqual(["a"]);
    expect(matchCustom(list, { genres: ["다큐"] }).map((e) => e.id)).toEqual(["b"]);
  });
});
