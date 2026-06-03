import * as amplitude from "@amplitude/analytics-browser";

// The Amplitude write key is public by design (it only authorizes sending
// events from the browser), so a committed fallback keeps the build working
// without a deploy-time secret — same pattern as the Supabase anon key.
const API_KEY =
  process.env.NEXT_PUBLIC_AMPLITUDE_API_KEY ??
  "163467815a1f0224b652bdb1e67bec8c";

let started = false;

/**
 * Initialise Amplitude once, on the client only. Safe to call repeatedly —
 * subsequent calls no-op. Autocapture handles page views, sessions, marketing
 * attribution, form interactions, file downloads and element clicks; the
 * `track*` helpers below add the high-value semantic events on top.
 */
export function initAnalytics(): void {
  if (started || typeof window === "undefined" || !API_KEY) return;
  // Don't send events from the (jsdom) test runner.
  if (process.env.NODE_ENV === "test") return;
  started = true;
  amplitude.init(API_KEY, {
    autocapture: true,
  });
}

// Effects in child components fire before the root provider's effect (effects
// run bottom-up), so any track() call must be able to bring Amplitude up itself.
function ready(): boolean {
  if (typeof window === "undefined") return false;
  if (!started) initAnalytics();
  return started;
}

/** Fire a custom event. No-ops during SSR / before init. */
export function track(event: string, props?: Record<string, unknown>): void {
  if (!ready()) return;
  amplitude.track(event, props);
}

/** Tie subsequent events to a signed-in user and stamp a few user properties. */
export function identifyUser(
  userId: string,
  traits?: Record<string, unknown>,
): void {
  if (!ready()) return;
  amplitude.setUserId(userId);
  if (traits) {
    const id = new amplitude.Identify();
    for (const [key, value] of Object.entries(traits)) {
      if (value !== undefined && value !== null) id.set(key, value as never);
    }
    amplitude.identify(id);
  }
}

/** Set a single user property (e.g. preferred locale). */
export function setUserProperty(key: string, value: unknown): void {
  if (!ready() || value === undefined || value === null) return;
  const id = new amplitude.Identify();
  id.set(key, value as never);
  amplitude.identify(id);
}

/** Clear identity on sign-out so the next session starts anonymous. */
export function resetUser(): void {
  if (!ready()) return;
  amplitude.reset();
}

// Event name constants — one source of truth so dashboards stay consistent.
export const EVENTS = {
  signInClicked: "sign_in_clicked",
  signedOut: "signed_out",
  exhibitionView: "exhibition_view",
  exhibitionScrap: "exhibition_scrap",
  swipeAction: "swipe_action",
  swipeShare: "swipe_share",
  homeViewMode: "home_view_mode",
  searchQuery: "search_query",
  sortChange: "sort_change",
  languageChange: "language_change",
  mapLocate: "map_locate",
  venueSheetOpen: "venue_sheet_open",
  sourceLinkClick: "source_link_click",
  feedbackSubmit: "feedback_submit",
  subscriptionToggle: "subscription_toggle",
  pwaInstallPrompt: "pwa_install_prompt",
} as const;
