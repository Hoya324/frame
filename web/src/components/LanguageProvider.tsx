"use client";
import { createContext, useCallback, useContext, useEffect, useState } from "react";
import { DEFAULT_LOCALE, LOCALES, translate, type Locale } from "@/lib/i18n";

const STORAGE_KEY = "frame.locale";

interface LangCtx {
  locale: Locale;
  setLocale: (l: Locale) => void;
  t: (key: string) => string;
}

const Ctx = createContext<LangCtx | null>(null);

export function LanguageProvider({ children }: { children: React.ReactNode }) {
  const [locale, setLocaleState] = useState<Locale>(DEFAULT_LOCALE);

  useEffect(() => {
    const saved = localStorage.getItem(STORAGE_KEY);
    if (saved && (LOCALES as string[]).includes(saved)) setLocaleState(saved as Locale);
  }, []);

  const setLocale = useCallback((l: Locale) => {
    setLocaleState(l);
    localStorage.setItem(STORAGE_KEY, l);
    document.documentElement.lang = l;
  }, []);

  const t = useCallback((key: string) => translate(locale, key), [locale]);

  return <Ctx.Provider value={{ locale, setLocale, t }}>{children}</Ctx.Provider>;
}

export function useLang(): LangCtx {
  const ctx = useContext(Ctx);
  if (!ctx) throw new Error("useLang must be used within LanguageProvider");
  return ctx;
}
