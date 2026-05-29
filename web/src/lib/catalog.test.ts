import { describe, expect, it } from "vitest";
import { parseCatalog, type Catalog } from "@/lib/catalog";

const RAW = {
  generated_at: "2026-05-30T06:54:00+00:00",
  exhibitions: [
    {
      id: "e1", title: "빛과 시간의 기록", title_en: null,
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
  venues: [{ id: "v1", name: "한미", name_en: null, venue_type: "museum",
    region: "서울", district: "삼청", address: "a", country: "KR",
    lat: 37.5, lng: 126.9, website: null }],
  artists: [{ id: "a1", name: "김작가", name_en: null }],
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
