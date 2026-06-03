// One-time onboarding walkthrough state. The "seen" flag lives in localStorage
// (versioned so a future revision can re-show the tour) — same gating pattern
// as the PWA install prompt's dismiss key. Step definitions are data so the
// provider/overlay stay generic and the order is testable.

export const ONBOARDING_KEY = "frame.onboarding.v1";

export interface OnboardingStep {
  id: string;
  /** Route this step is shown on; the provider navigates here when entering it. */
  route: string;
  titleKey: string;
  bodyKey: string;
  /** "swipe" steps switch the discover view into swipe mode while active. */
  kind?: "swipe";
}

export const ONBOARDING_STEPS: OnboardingStep[] = [
  { id: "welcome", route: "/", titleKey: "onb.welcome.title", bodyKey: "onb.welcome.body" },
  { id: "timeline", route: "/", titleKey: "onb.timeline.title", bodyKey: "onb.timeline.body" },
  { id: "swipe", route: "/", titleKey: "onb.swipe.title", bodyKey: "onb.swipe.body", kind: "swipe" },
  { id: "scrap", route: "/scrap", titleKey: "onb.scrap.title", bodyKey: "onb.scrap.body" },
  { id: "subscribe", route: "/me", titleKey: "onb.subscribe.title", bodyKey: "onb.subscribe.body" },
  { id: "feedback", route: "/me", titleKey: "onb.feedback.title", bodyKey: "onb.feedback.body" },
];

// In-progress tour state, persisted to sessionStorage so the walkthrough
// survives a full remount. The deployed app is a static export served through
// a service worker, so a tab-to-tab navigation can trigger a hard page load
// that wipes React state — without this the tour would silently vanish
// mid-flow (e.g. "stops at the scrap step"). sessionStorage is per-tab and
// survives reloads, but not a brand-new visit, which is exactly the scope we want.
const PROGRESS_KEY = "frame.onboarding.progress";

export interface OnboardingProgress {
  active: boolean;
  stepIndex: number;
}

export function readOnboardingProgress(): OnboardingProgress | null {
  if (typeof sessionStorage === "undefined") return null;
  try {
    const raw = sessionStorage.getItem(PROGRESS_KEY);
    if (!raw) return null;
    const p = JSON.parse(raw) as OnboardingProgress;
    if (typeof p?.active !== "boolean" || typeof p?.stepIndex !== "number") return null;
    return p;
  } catch {
    return null;
  }
}

export function writeOnboardingProgress(p: OnboardingProgress): void {
  if (typeof sessionStorage === "undefined") return;
  try {
    sessionStorage.setItem(PROGRESS_KEY, JSON.stringify(p));
  } catch {
    // storage full / disabled — non-fatal
  }
}

export function clearOnboardingProgress(): void {
  if (typeof sessionStorage === "undefined") return;
  try {
    sessionStorage.removeItem(PROGRESS_KEY);
  } catch {
    // non-fatal
  }
}

export function hasSeenOnboarding(): boolean {
  if (typeof localStorage === "undefined") return false;
  return localStorage.getItem(ONBOARDING_KEY) != null;
}

export function markOnboardingSeen(): void {
  if (typeof localStorage === "undefined") return;
  localStorage.setItem(ONBOARDING_KEY, "1");
}

export function resetOnboarding(): void {
  if (typeof localStorage === "undefined") return;
  localStorage.removeItem(ONBOARDING_KEY);
}
