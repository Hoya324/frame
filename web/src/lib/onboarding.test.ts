import { beforeEach, describe, expect, it } from "vitest";
import {
  ONBOARDING_KEY,
  ONBOARDING_STEPS,
  clearOnboardingProgress,
  hasSeenOnboarding,
  markOnboardingSeen,
  readOnboardingProgress,
  resetOnboarding,
  writeOnboardingProgress,
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

describe("onboarding progress (survives remount)", () => {
  beforeEach(() => sessionStorage.clear());

  it("is null by default", () => {
    expect(readOnboardingProgress()).toBeNull();
  });

  it("round-trips active step state", () => {
    writeOnboardingProgress({ active: true, stepIndex: 3 });
    expect(readOnboardingProgress()).toEqual({ active: true, stepIndex: 3 });
  });

  it("clears progress", () => {
    writeOnboardingProgress({ active: true, stepIndex: 2 });
    clearOnboardingProgress();
    expect(readOnboardingProgress()).toBeNull();
  });

  it("ignores malformed payloads", () => {
    sessionStorage.setItem("frame.onboarding.progress", "{not json");
    expect(readOnboardingProgress()).toBeNull();
  });
});

describe("ONBOARDING_STEPS", () => {
  it("follows the welcome → timeline → swipe → scrap → subscribe → feedback → install order", () => {
    expect(ONBOARDING_STEPS.map((s) => s.id)).toEqual([
      "welcome",
      "timeline",
      "swipe",
      "scrap",
      "subscribe",
      "feedback",
      "install",
    ]);
  });

  it("routes the discover steps to /, scrap to /scrap, account steps to /me, install back to /", () => {
    const route = (id: string) => ONBOARDING_STEPS.find((s) => s.id === id)?.route;
    expect(route("welcome")).toBe("/");
    expect(route("timeline")).toBe("/");
    expect(route("swipe")).toBe("/");
    expect(route("scrap")).toBe("/scrap");
    expect(route("subscribe")).toBe("/me");
    expect(route("feedback")).toBe("/me");
    expect(route("install")).toBe("/");
  });

  it("flags only the swipe step as the swipe kind and the install step as install", () => {
    expect(ONBOARDING_STEPS.filter((s) => s.kind === "swipe").map((s) => s.id)).toEqual(["swipe"]);
    expect(ONBOARDING_STEPS.filter((s) => s.kind === "install").map((s) => s.id)).toEqual(["install"]);
  });

  it("gives every step a title and body i18n key", () => {
    for (const s of ONBOARDING_STEPS) {
      expect(s.titleKey).toMatch(/^onb\./);
      expect(s.bodyKey).toMatch(/^onb\./);
    }
  });
});
