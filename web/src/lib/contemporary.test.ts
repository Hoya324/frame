import { describe, expect, it } from "vitest";
import { CONTEMPORARY } from "./contemporary";
import { LOCALES } from "./i18n";

describe("CONTEMPORARY rail data", () => {
  it("has unique ids", () => {
    const ids = CONTEMPORARY.map((m) => m.id);
    expect(new Set(ids).size).toBe(ids.length);
  });

  it("links out over https only", () => {
    for (const m of CONTEMPORARY) expect(m.url).toMatch(/^https:\/\//);
  });

  it("provides every locale for name and line", () => {
    for (const m of CONTEMPORARY) {
      for (const l of LOCALES) {
        expect(m.name[l], `${m.id} name.${l}`).toBeTruthy();
        expect(m.line[l], `${m.id} line.${l}`).toBeTruthy();
      }
    }
  });

  it("has enough entries to fill the widest viewport (6 visible)", () => {
    expect(CONTEMPORARY.length).toBeGreaterThanOrEqual(8);
  });
});
