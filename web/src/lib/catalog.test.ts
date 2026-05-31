import { describe, expect, it } from "vitest";
import { parseCatalog, localized, type Catalog } from "@/lib/catalog";

const RAW = {
  generated_at: "2026-05-30T06:54:00+00:00",
  exhibitions: [
    {
      id: "e1", title: "빛과 시간의 기록",
      poster_image_url: "https://x/p.jpg", description: "d",
      medium: "photo", exhibition_type: "solo", genre_tags: ["doc"],
      fee_type: "free", price_min: null, price_max: null,
      start_date: "2026-05-30", end_date: "2026-07-20",
      status: "ongoing", open_hours: "10-18",
      venue: { id: "v1", name: "한미", region: "서울", district: "삼청", lat: 37.5, lng: 126.9 },
      artists: [{ id: "a1", name: "김작가" }],
      source_url: "https://s/1", featured: true, popularity_score: null,
    },
  ],
  venues: [{ id: "v1", name: "한미", venue_type: "museum",
    region: "서울", district: "삼청", address: "a", country: "KR",
    lat: 37.5, lng: 126.9, website: null }],
  artists: [{ id: "a1", name: "김작가" }],
};

const raw = {
  generated_at: "2026-05-31T00:00:00Z",
  exhibitions: [{
    id: "e1", title: "戎康友 展", lang: "ja",
    tr: { ko: { title: "에비스 전", description: "캘리포니아" } },
    description: "カリフォルニア",
    venue: { id: "v1", name: "BOOK AND SONS", lang: "en", tr: { ko: { name: "북앤선즈" } } },
    artists: [{ id: "a1", name: "戎康友", tr: { ko: { name: "에비스" } } }],
  }],
  venues: [], artists: [],
};

describe("parseCatalog", () => {
  it("parses into typed catalog", () => {
    const cat: Catalog = parseCatalog(RAW);
    expect(cat.exhibitions).toHaveLength(1);
    expect(cat.exhibitions[0].venue?.district).toBe("삼청");
    expect(cat.exhibitions[0].featured).toBe(true);
    expect(cat.generatedAt).toBe("2026-05-30T06:54:00+00:00");
  });
});

describe("parseCatalog tr/lang", () => {
  it("parses tr and lang onto exhibition, venue, artist", () => {
    const c = parseCatalog(raw);
    const e = c.exhibitions[0];
    expect(e.lang).toBe("ja");
    expect(e.tr.ko?.title).toBe("에비스 전");
    expect(e.venue?.tr.ko?.name).toBe("북앤선즈");
    expect(e.artists[0].tr.ko?.name).toBe("에비스");
  });
});

describe("localized", () => {
  it("returns translation when present for locale", () => {
    expect(localized("戎康友 展", { ko: { title: "에비스 전" } }, "ko", "title")).toBe("에비스 전");
  });
  it("returns null when no translation for locale (treat as original)", () => {
    expect(localized("을지로의 밤", {}, "ko", "title")).toBeNull();
    expect(localized("戎康友 展", { ko: { title: "에비스 전" } }, "ja", "title")).toBeNull();
  });
});
