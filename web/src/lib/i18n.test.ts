import { describe, expect, it } from "vitest";
import { LOCALES, translate } from "./i18n";

const CINEMA_KEYS = [
  "cinema.title",
  "cinema.subtitle",
  "cinema.pdLabel",
  "cinema.modernLabel",
  "cinema.modernNote",
];

describe("i18n cinema keys", () => {
  it("resolves every cinema key in every locale (not the raw key back)", () => {
    for (const key of CINEMA_KEYS) {
      for (const l of LOCALES) {
        const v = translate(l, key);
        expect(v, `${key}@${l}`).toBeTruthy();
        expect(v, `${key}@${l} fell through to the key`).not.toBe(key);
      }
    }
  });

  it("has a distinct translation per locale (no silent ko fallback)", () => {
    // translate() falls back to ko for a missing locale entry; if en/ja equalled
    // ko it would mean the key was never translated. These strings are all
    // genuinely different per language, so equality flags a missing key.
    for (const key of CINEMA_KEYS) {
      const ko = translate("ko", key);
      expect(translate("en", key), `${key} en missing`).not.toBe(ko);
      expect(translate("ja", key), `${key} ja missing`).not.toBe(ko);
    }
  });

  it("returns the key itself for an unknown key (fallback contract)", () => {
    expect(translate("ko", "cinema.__nope__")).toBe("cinema.__nope__");
  });
});
