// Shared PWA-install store. The browser fires `beforeinstallprompt` once, very
// early, and only the code that captured that event can later call prompt() to
// trigger the real one-click native install. We capture it in a single module
// store so both the floating InstallPrompt banner and the onboarding final step
// can offer one-click install from the same captured event (read via
// useSyncExternalStore). iOS Safari has no such event — callers fall back to
// manual "Share → Add to Home Screen" instructions.

export interface BeforeInstallPromptEvent extends Event {
  prompt: () => Promise<void>;
  userChoice: Promise<{ outcome: "accepted" | "dismissed" }>;
}

let deferred: BeforeInstallPromptEvent | null = null;
let initialized = false;
const listeners = new Set<() => void>();

function emit() {
  listeners.forEach((l) => l());
}

/** Register the global listeners once. Safe to call from multiple components. */
export function initPwaInstall(): void {
  if (initialized || typeof window === "undefined") return;
  initialized = true;
  window.addEventListener("beforeinstallprompt", (e) => {
    e.preventDefault();
    deferred = e as BeforeInstallPromptEvent;
    emit();
  });
  window.addEventListener("appinstalled", () => {
    deferred = null;
    emit();
  });
}

export function subscribeInstall(cb: () => void): () => void {
  listeners.add(cb);
  return () => {
    listeners.delete(cb);
  };
}

/** useSyncExternalStore snapshot: is a one-click native install available now? */
export function getCanInstall(): boolean {
  return deferred !== null;
}

export function getServerCanInstall(): boolean {
  return false;
}

/** Trigger the native install dialog. Returns the user's choice, or
 * "unavailable" when there is no captured prompt (e.g. iOS, or already installed). */
export async function promptInstall(): Promise<"accepted" | "dismissed" | "unavailable"> {
  const evt = deferred;
  if (!evt) return "unavailable";
  await evt.prompt();
  const { outcome } = await evt.userChoice;
  // The event can only be used once; drop it either way.
  deferred = null;
  emit();
  return outcome;
}

export function isStandalone(): boolean {
  if (typeof window === "undefined") return false;
  return (
    window.matchMedia?.("(display-mode: standalone)").matches === true ||
    (window.navigator as { standalone?: boolean }).standalone === true
  );
}
