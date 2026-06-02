import { DEFAULT_LOCALE, LOCALES, type Locale } from "@/lib/i18n";

// The locale lives in localStorage so it survives reloads and is available
// before auth resolves. It is shared as a tiny external store (read via
// useSyncExternalStore in LanguageProvider) so both the provider and the
// account-sync effect mutate one source of truth without prop-drilling.
const STORAGE_KEY = "frame.locale";
const listeners = new Set<() => void>();

export function getStoredLocale(): Locale {
  if (typeof localStorage === "undefined") return DEFAULT_LOCALE;
  const saved = localStorage.getItem(STORAGE_KEY);
  return saved && (LOCALES as string[]).includes(saved) ? (saved as Locale) : DEFAULT_LOCALE;
}

export function getServerLocale(): Locale {
  return DEFAULT_LOCALE;
}

export function setStoredLocale(l: Locale): void {
  if (typeof localStorage !== "undefined") localStorage.setItem(STORAGE_KEY, l);
  if (typeof document !== "undefined") document.documentElement.lang = l;
  listeners.forEach((cb) => cb());
}

export function subscribeLocale(cb: () => void): () => void {
  listeners.add(cb);
  return () => {
    listeners.delete(cb);
  };
}
