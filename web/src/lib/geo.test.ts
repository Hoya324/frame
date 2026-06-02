import { describe, expect, it } from "vitest";
import { distanceKm } from "@/lib/geo";

describe("distanceKm", () => {
  it("is zero for identical points", () => {
    expect(distanceKm([126.98, 37.57], [126.98, 37.57])).toBeCloseTo(0, 5);
  });
  it("approximates Seoul→Busan (~325km)", () => {
    const d = distanceKm([126.978, 37.566], [129.075, 35.18]);
    expect(d).toBeGreaterThan(300);
    expect(d).toBeLessThan(340);
  });
});
