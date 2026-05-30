import { describe, expect, it } from "vitest";
import { renderDigest, renderClosingSoon } from "./render";
import type { JobExhibition } from "./catalog";

function ex(id: string, title: string): JobExhibition {
  return {
    id, title, medium: "photo", exhibitionType: "solo", genreTags: [], feeType: "free",
    startDate: "2026-05-01", endDate: "2026-06-02", status: "ongoing",
    posterImageUrl: "https://x/p.jpg", sourceUrl: "https://s/1", venueName: "한미", region: "서울",
    artistNames: ["김작가"],
  };
}

describe("render", () => {
  it("renderDigest includes each exhibition title and a link to the site detail", () => {
    const html = renderDigest([ex("e1", "빛"), ex("e2", "그림자")], "https://frame.example");
    expect(html).toContain("빛");
    expect(html).toContain("그림자");
    expect(html).toContain("https://frame.example/exhibitions/e1");
  });
  it("renderClosingSoon shows the D-day per item", () => {
    const html = renderClosingSoon([{ e: ex("e1", "빛"), dday: 3 }], "https://frame.example");
    expect(html).toContain("D-3");
    expect(html).toContain("빛");
  });
});
