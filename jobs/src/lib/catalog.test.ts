import { describe, expect, it } from "vitest";
import { parseCatalog, daysUntil, type JobExhibition } from "./catalog";

const RAW = {
  generated_at: "2026-05-30T00:00:00Z",
  exhibitions: [{
    id: "e1", title: "T", medium: "photo", exhibition_type: "solo",
    genre_tags: ["doc"], fee_type: "free", start_date: "2026-05-01", end_date: "2026-06-02",
    status: "ongoing", poster_image_url: "p", source_url: "s",
    tr: { en: { title: "Title EN" }, ja: { title: "タイトル" } },
    venue: {
      id: "v", name: "한미", region: "서울", district: "삼청", lat: 37.5, lng: 126.9,
      tr: { en: { name: "Museum Hanmi" } },
    },
    artists: [{ id: "a", name: "김작가" }],
  }],
  venues: [], artists: [],
};

describe("jobs catalog", () => {
  it("parses to typed exhibitions", () => {
    const cat = parseCatalog(RAW);
    const e: JobExhibition = cat.exhibitions[0];
    expect(e.id).toBe("e1");
    expect(e.region).toBe("서울");
    expect(e.artistNames).toEqual(["김작가"]);
    expect(e.genreTags).toEqual(["doc"]);
  });

  it("parses per-field translations for title and venue name", () => {
    const e = parseCatalog(RAW).exhibitions[0];
    expect(e.titleTr).toEqual({ en: "Title EN", ja: "タイトル" });
    expect(e.venueNameTr).toEqual({ en: "Museum Hanmi" });
  });

  it("daysUntil counts whole days from a fixed today", () => {
    const today = new Date("2026-05-30T00:00:00+09:00");
    expect(daysUntil("2026-06-02", today)).toBe(3);
    expect(daysUntil("2026-05-31", today)).toBe(1);
    expect(daysUntil(null, today)).toBeNull();
  });
});
