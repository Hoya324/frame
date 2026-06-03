import { beforeEach, describe, expect, it } from "vitest";
import {
  ONBOARDING_KEY,
  ONBOARDING_STEPS,
  hasSeenOnboarding,
  markOnboardingSeen,
  resetOnboarding,
} from "@/lib/onboarding";

describe("onboarding localStorage gating", () => {
  beforeEach(() => localStorage.clear());

  it("is unseen by default", () => {
    expect(hasSeenOnboarding()).toBe(false);
  });

  it("marks as seen and persists", () => {
    markOnboardingSeen();
    expect(localStorage.getItem(ONBOARDING_KEY)).toBeTruthy();
    expect(hasSeenOnboarding()).toBe(true);
  });

  it("reset clears the seen flag", () => {
    markOnboardingSeen();
    resetOnboarding();
    expect(hasSeenOnboarding()).toBe(false);
  });
});

describe("ONBOARDING_STEPS", () => {
  it("follows the welcome → timeline → swipe → scrap → subscribe → feedback order", () => {
    expect(ONBOARDING_STEPS.map((s) => s.id)).toEqual([
      "welcome",
      "timeline",
      "swipe",
      "scrap",
      "subscribe",
      "feedback",
    ]);
  });

  it("routes the discover steps to /, scrap to /scrap, account steps to /me", () => {
    const route = (id: string) => ONBOARDING_STEPS.find((s) => s.id === id)?.route;
    expect(route("welcome")).toBe("/");
    expect(route("timeline")).toBe("/");
    expect(route("swipe")).toBe("/");
    expect(route("scrap")).toBe("/scrap");
    expect(route("subscribe")).toBe("/me");
    expect(route("feedback")).toBe("/me");
  });

  it("flags only the swipe step as the swipe kind", () => {
    expect(ONBOARDING_STEPS.filter((s) => s.kind === "swipe").map((s) => s.id)).toEqual(["swipe"]);
  });

  it("gives every step a title and body i18n key", () => {
    for (const s of ONBOARDING_STEPS) {
      expect(s.titleKey).toMatch(/^onb\./);
      expect(s.bodyKey).toMatch(/^onb\./);
    }
  });
});
