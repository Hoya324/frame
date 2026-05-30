export const DISMISS_KEY = "frame.pwa.dismissedAt";
export const DISMISS_DAYS = 7;

const DAY_MS = 24 * 60 * 60 * 1000;

/** A dismissal is still active (banner stays hidden) within the cooldown window. */
export function isDismissActive(
  dismissedAt: number | null,
  now: number,
  days = DISMISS_DAYS,
): boolean {
  if (!dismissedAt) return false;
  return now - dismissedAt < days * DAY_MS;
}

/** iOS, including iPadOS 13+ which reports a "Macintosh" UA but exposes touch. */
export function isIOS(ua: string, maxTouchPoints = 0): boolean {
  if (/iphone|ipad|ipod/i.test(ua)) return true;
  return /Macintosh/i.test(ua) && maxTouchPoints > 1;
}

/** Safari proper — excludes Chrome/Firefox/Edge on iOS, which use WebKit but a different UA. */
export function isSafari(ua: string): boolean {
  return /safari/i.test(ua) && !/(crios|fxios|edgios|chrome|android)/i.test(ua);
}

export type PromptMode = "none" | "install" | "ios";

/**
 * Decide which install affordance to render.
 * - `install`: a captured beforeinstallprompt is ready (Android/desktop Chrome).
 * - `ios`: iOS Safari, which has no beforeinstallprompt — show manual instructions.
 * - `none`: already installed, recently dismissed, or no path to install.
 */
export function decidePromptMode(opts: {
  standalone: boolean;
  dismissed: boolean;
  hasDeferredPrompt: boolean;
  iosSafari: boolean;
}): PromptMode {
  if (opts.standalone || opts.dismissed) return "none";
  if (opts.hasDeferredPrompt) return "install";
  if (opts.iosSafari) return "ios";
  return "none";
}
