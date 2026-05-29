import { describe, expect, it } from "vitest";
import { daysUntil, ddayLabel, isClosingSoon } from "@/lib/status";

const TODAY = new Date("2026-05-30T00:00:00+09:00");

describe("status helpers", () => {
  it("daysUntil counts whole days to end date", () => {
    expect(daysUntil("2026-06-02", TODAY)).toBe(3);
    expect(daysUntil("2026-05-30", TODAY)).toBe(0);
    expect(daysUntil(null, TODAY)).toBeNull();
  });
  it("ddayLabel formats", () => {
    expect(ddayLabel("2026-06-02", TODAY)).toBe("D-3");
    expect(ddayLabel("2026-05-30", TODAY)).toBe("D-day");
    expect(ddayLabel(null, TODAY)).toBeNull();
  });
  it("isClosingSoon within 7 days inclusive", () => {
    expect(isClosingSoon("2026-06-06", TODAY)).toBe(true);
    expect(isClosingSoon("2026-06-30", TODAY)).toBe(false);
    expect(isClosingSoon(null, TODAY)).toBe(false);
  });
});
