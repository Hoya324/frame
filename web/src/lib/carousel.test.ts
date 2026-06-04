import { describe, expect, it } from "vitest";
import { buildCarouselSlides } from "./carousel";
import type { Master } from "./masters";

function master(id: string): Master {
  return {
    id, name: id, region: "foreign", nationality: "US", birthYear: 1900, deathYear: 1980,
    tagline: "t", bio: "b", portraitUrl: `https://x/${id}.jpg`, lang: "ko", tr: {},
    works: [{ id: `${id}-1`, title: "w", year: "1900", medium: "m",
      imageUrl: `https://x/${id}-1.jpg`, thumbUrl: `https://x/${id}-1t.jpg`,
      source: "the_met", sourceUrl: "https://x/1", credit: "c", commentary: "c",
      lang: "ko", tr: {} }],
  };
}

// deterministic RNG for tests
function seeded(seq: number[]): () => number {
  let i = 0;
  return () => seq[i++ % seq.length];
}

// eslint-disable-next-line @typescript-eslint/no-explicit-any
const exhibitions = [{ id: "e1" }, { id: "e2" }] as any[];

describe("buildCarouselSlides", () => {
  it("includes exhibition slides and master slides", () => {
    const slides = buildCarouselSlides(exhibitions, [master("a"), master("b")], {
      masterCount: 2, rng: seeded([0]),
    });
    const kinds = slides.map((s) => s.kind);
    expect(kinds).toContain("exhibition");
    expect(kinds).toContain("master");
  });

  it("limits master slides to masterCount and only uses ones with an image", () => {
    const noImg = master("z");
    noImg.portraitUrl = null;
    noImg.works = [];
    const slides = buildCarouselSlides([], [master("a"), master("b"), noImg], {
      masterCount: 2, rng: seeded([0]),
    });
    const masterSlides = slides.filter((s) => s.kind === "master");
    expect(masterSlides).toHaveLength(2);
    expect(masterSlides.every((s) => s.kind === "master" && s.image)).toBe(true);
  });

  it("is randomized by rng (different seed → different first master)", () => {
    const ms = [master("a"), master("b"), master("c"), master("d")];
    const first = buildCarouselSlides([], ms, { masterCount: 1, rng: seeded([0]) })
      .find((s) => s.kind === "master");
    const second = buildCarouselSlides([], ms, { masterCount: 1, rng: seeded([0.99]) })
      .find((s) => s.kind === "master");
    expect(first?.id).not.toBe(second?.id);
  });
});
