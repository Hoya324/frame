"use client";
import { createContext, useCallback, useContext, useSyncExternalStore } from "react";
import { DEFAULT_LOCALE, LOCALES, translate, type Locale } from "@/lib/i18n";

const STORAGE_KEY = "frame.locale";

// The persisted locale is external state (localStorage), so we read it through
// useSyncExternalStore instead of an effect+setState. This stays hydration-safe
// (the server snapshot is the default; the client adopts the stored value after
// hydration) without the cascading render the effect+setState pattern triggers.
const listeners = new Set<() => void>();

function getSnapshot(): Locale {
  const saved = localStorage.getItem(STORAGE_KEY);
  return saved && (LOCALES as string[]).includes(saved) ? (saved as Locale) : DEFAULT_LOCALE;
}

function getServerSnapshot(): Locale {
  return DEFAULT_LOCALE;
}

function subscribe(cb: () => void): () => void {
  listeners.add(cb);
  return () => {
    listeners.delete(cb);
  };
}

interface LangCtx {
  locale: Locale;
  setLocale: (l: Locale) => void;
  t: (key: string) => string;
}

const Ctx = createContext<LangCtx | null>(null);

export function LanguageProvider({ children }: { children: React.ReactNode }) {
  const locale = useSyncExternalStore(subscribe, getSnapshot, getServerSnapshot);

  const setLocale = useCallback((l: Locale) => {
    localStorage.setItem(STORAGE_KEY, l);
    document.documentElement.lang = l;
    listeners.forEach((cb) => cb());
  }, []);

  const t = useCallback((key: string) => translate(locale, key), [locale]);

  return <Ctx.Provider value={{ locale, setLocale, t }}>{children}</Ctx.Provider>;
}

export function useLang(): LangCtx {
  const ctx = useContext(Ctx);
  if (!ctx) throw new Error("useLang must be used within LanguageProvider");
  return ctx;
}
