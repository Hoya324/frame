import { describe, expect, it } from "vitest";
import { CINEMA_MODERN, CINEMA_PD } from "./cinema";
import { LOCALES } from "./i18n";

describe("cinema curation data", () => {
  const all = [...CINEMA_PD, ...CINEMA_MODERN];

  it("has unique ids across both groups", () => {
    const ids = all.map((s) => s.id);
    expect(new Set(ids).size).toBe(ids.length);
  });

  it("links out over https only", () => {
    for (const s of all) expect(s.url, s.id).toMatch(/^https:\/\//);
  });

  it("localises title, credit and lesson for every locale", () => {
    for (const s of all) {
      for (const l of LOCALES) {
        expect(s.title[l], `${s.id} title.${l}`).toBeTruthy();
        expect(s.credit[l], `${s.id} credit.${l}`).toBeTruthy();
        expect(s.lesson[l], `${s.id} lesson.${l}`).toBeTruthy();
      }
    }
  });

  it("PD scenes host a Wikimedia image and need no studio credit", () => {
    for (const s of CINEMA_PD) {
      expect(s.image, s.id).toMatch(/^https:\/\/upload\.wikimedia\.org\//);
    }
  });

  it("modern (in-copyright) scenes always carry a © studio credit", () => {
    // The 인용 (quotation) basis requires attribution — a modern entry without
    // a studio credit must never reach the UI.
    for (const s of CINEMA_MODERN) {
      expect(s.studio, s.id).toBeTruthy();
    }
  });

  it("modern stills are low-res TMDB images (the 인용 'amount' factor)", () => {
    for (const s of CINEMA_MODERN) {
      // sourced as a low-res still, not the studio's full-res master
      expect(s.image, s.id).toMatch(/^https:\/\/image\.tmdb\.org\/t\/p\/w\d+\//);
    }
  });

  it("modern films carry a gallery and a trilingual curation for the detail page", () => {
    for (const s of CINEMA_MODERN) {
      expect(s.gallery?.length ?? 0, s.id).toBeGreaterThanOrEqual(1);
      for (const g of s.gallery ?? []) {
        expect(g, s.id).toMatch(/^https:\/\/image\.tmdb\.org\//);
      }
      for (const l of LOCALES) {
        expect(s.curation?.[l], `${s.id} curation.${l}`).toBeTruthy();
      }
    }
  });
});
