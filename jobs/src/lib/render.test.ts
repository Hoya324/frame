import { describe, expect, it } from "vitest";
import { renderDigest, renderClosingSoon, emailStrings } from "./render";
import type { JobExhibition } from "./catalog";

function ex(id: string, title: string, extra: Partial<JobExhibition> = {}): JobExhibition {
  return {
    id, title, titleTr: {}, medium: "photo", exhibitionType: "solo", genreTags: [], feeType: "free",
    startDate: "2026-05-01", endDate: "2026-06-02", status: "ongoing",
    posterImageUrl: "https://x/p.jpg", sourceUrl: "https://s/1", venueName: "한미", venueNameTr: {},
    region: "서울", artistNames: ["김작가"], ...extra,
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

  it("uses the locale's chrome strings (section title)", () => {
    const en = renderDigest([ex("e1", "빛")], "https://frame.example", "en");
    expect(en).toContain(emailStrings("en").digestTitle);
    expect(en).not.toContain(emailStrings("ko").digestTitle);
  });

  it("shows the translated title with the original underneath when a translation exists", () => {
    const e = ex("e1", "빛", { titleTr: { en: "Light" }, venueName: "한미", venueNameTr: { en: "Museum Hanmi" } });
    const html = renderDigest([e], "https://frame.example", "en");
    expect(html).toContain("Light");        // translation (primary)
    expect(html).toContain("빛");            // original (secondary)
    expect(html).toContain("Museum Hanmi");  // venue translation
    expect(html).toContain("한미");          // venue original
  });

  it("shows the original only when there is no translation for the locale", () => {
    const e = ex("e1", "빛", { titleTr: {} });
    const html = renderDigest([e], "https://frame.example", "en");
    // The original appears once as the primary line; no duplicate 'secondary'.
    expect(html.match(/빛/g)?.length).toBe(1);
  });
});
