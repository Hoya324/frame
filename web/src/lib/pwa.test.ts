import { describe, expect, it } from "vitest";
import { decidePromptMode, isDismissActive, isIOS, isSafari } from "@/lib/pwa";

const DAY = 24 * 60 * 60 * 1000;

describe("isDismissActive", () => {
  it("is inactive when never dismissed", () => {
    expect(isDismissActive(null, 1_000_000)).toBe(false);
  });
  it("stays active within the 7-day window", () => {
    const now = 10 * DAY;
    expect(isDismissActive(now - 6 * DAY, now)).toBe(true);
  });
  it("expires after the window", () => {
    const now = 10 * DAY;
    expect(isDismissActive(now - 8 * DAY, now)).toBe(false);
  });
});

describe("isIOS", () => {
  it("detects iPhone", () => {
    expect(isIOS("Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X)")).toBe(true);
  });
  it("detects iPadOS masquerading as Macintosh when touch is present", () => {
    expect(isIOS("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15)", 5)).toBe(true);
  });
  it("treats a real Mac (no touch) as not iOS", () => {
    expect(isIOS("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15)", 0)).toBe(false);
  });
  it("is false for Android", () => {
    expect(isIOS("Mozilla/5.0 (Linux; Android 14)")).toBe(false);
  });
});

describe("isSafari", () => {
  it("is true for mobile Safari", () => {
    expect(
      isSafari("Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) Version/17.0 Safari/605"),
    ).toBe(true);
  });
  it("is false for Chrome on iOS (CriOS)", () => {
    expect(isSafari("Mozilla/5.0 (iPhone) CriOS/120 Mobile Safari/605")).toBe(false);
  });
  it("is false for Android Chrome", () => {
    expect(isSafari("Mozilla/5.0 (Linux; Android 14) Chrome/120 Safari/537")).toBe(false);
  });
});

describe("decidePromptMode", () => {
  const base = { standalone: false, dismissed: false, hasDeferredPrompt: false, iosSafari: false };

  it("returns none when already installed", () => {
    expect(decidePromptMode({ ...base, standalone: true, hasDeferredPrompt: true })).toBe("none");
  });
  it("returns none when recently dismissed", () => {
    expect(decidePromptMode({ ...base, dismissed: true, hasDeferredPrompt: true })).toBe("none");
  });
  it("returns install when a prompt is captured", () => {
    expect(decidePromptMode({ ...base, hasDeferredPrompt: true })).toBe("install");
  });
  it("returns ios for iOS Safari without a captured prompt", () => {
    expect(decidePromptMode({ ...base, iosSafari: true })).toBe("ios");
  });
  it("prefers the native install prompt over the iOS hint", () => {
    expect(decidePromptMode({ ...base, hasDeferredPrompt: true, iosSafari: true })).toBe("install");
  });
  it("returns none when no install path exists", () => {
    expect(decidePromptMode(base)).toBe("none");
  });
});
