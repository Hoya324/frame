import { describe, expect, it } from "vitest";
import { parseMasters } from "./masters";

const raw = {
  generated_at: "2026-06-05T00:00:00Z",
  masters: [
    {
      id: "atget", name: "Eugène Atget", lang: "ko", region: "foreign",
      nationality: "FR", birthYear: 1857, deathYear: 1927,
      tagline: "파리를 기록한 선구자", bio: "소개", portraitUrl: "https://x/a.jpg",
      tr: { en: { tagline: "Pioneer", bio: "about" }, ja: { name: "アジェ" } },
      works: [{
        id: "the_met-1", title: "Le Pont Neuf", year: "1900", medium: "Albumen",
        imageUrl: "https://x/1.jpg", thumbUrl: "https://x/1t.jpg", source: "the_met",
        sourceUrl: "https://x/1", credit: "Met · CC0", commentary: "해설",
        tr: { en: { commentary: "about" } },
      }],
    },
  ],
};

describe("parseMasters", () => {
  it("maps masters and works", () => {
    const cat = parseMasters(raw);
    expect(cat.masters).toHaveLength(1);
    const m = cat.masters[0];
    expect(m.id).toBe("atget");
    expect(m.region).toBe("foreign");
    expect(m.works[0].imageUrl).toBe("https://x/1.jpg");
    expect(m.tr.ja?.name).toBe("アジェ");
  });

  it("tolerates missing fields", () => {
    const cat = parseMasters({ generated_at: "x", masters: [{ id: "a", name: "A", works: [] }] });
    expect(cat.masters[0].works).toEqual([]);
    expect(cat.masters[0].region).toBe("foreign");
  });
});
