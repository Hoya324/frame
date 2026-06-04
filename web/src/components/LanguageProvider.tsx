"use client";
import { createContext, useCallback, useContext, useSyncExternalStore } from "react";
import { translate, type Locale } from "@/lib/i18n";
import {
  getServerLocale,
  getStoredLocale,
  setStoredLocale,
  subscribeLocale,
} from "@/lib/localeStore";

// The persisted locale is external state (localStorage), so we read it through
// useSyncExternalStore instead of an effect+setState. This stays hydration-safe
// (the server snapshot is the default; the client adopts the stored value after
// hydration) without the cascading render the effect+setState pattern triggers.
// The store itself lives in lib/localeStore so the account-sync effect
// (LocaleSync) can hydrate/persist it without going through React context.

interface LangCtx {
  locale: Locale;
  setLocale: (l: Locale) => void;
  t: (key: string, vars?: Record<string, string | number>) => string;
}

const Ctx = createContext<LangCtx | null>(null);

export function LanguageProvider({ children }: { children: React.ReactNode }) {
  const locale = useSyncExternalStore(subscribeLocale, getStoredLocale, getServerLocale);

  const setLocale = useCallback((l: Locale) => setStoredLocale(l), []);

  const t = useCallback((key: string, vars?: Record<string, string | number>) => {
    let s = translate(locale, key);
    if (vars) {
      for (const [k, v] of Object.entries(vars)) {
        s = s.replace(new RegExp(`\\{${k}\\}`, "g"), String(v));
      }
    }
    return s;
  }, [locale]);

  return <Ctx.Provider value={{ locale, setLocale, t }}>{children}</Ctx.Provider>;
}

export function useLang(): LangCtx {
  const ctx = useContext(Ctx);
  if (!ctx) throw new Error("useLang must be used within LanguageProvider");
  return ctx;
}
