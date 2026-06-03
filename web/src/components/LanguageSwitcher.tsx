"use client";
import { useState } from "react";
import { Globe, Check } from "lucide-react";
import { useLang } from "@/components/LanguageProvider";
import { LOCALES, LOCALE_LABEL, type Locale } from "@/lib/i18n";
import { EVENTS, track } from "@/lib/analytics";

export function LanguageSwitcher() {
  const { locale, setLocale } = useLang();
  const [open, setOpen] = useState(false);
  const pick = (l: Locale) => {
    if (l !== locale) track(EVENTS.languageChange, { locale: l, from: locale });
    setLocale(l);
    setOpen(false);
  };

  return (
    <div className="relative">
      <button
        type="button"
        aria-label="언어 선택"
        onClick={() => setOpen((o) => !o)}
        className="flex items-center gap-1.5 rounded-md px-2.5 py-1.5 text-sm text-tx2 transition hover:text-tx"
      >
        <Globe size={16} />
        <span className="hidden sm:inline">{LOCALE_LABEL[locale]}</span>
      </button>
      {open && (
        <>
          <div className="fixed inset-0 z-30" onClick={() => setOpen(false)} aria-hidden />
          <div className="absolute right-0 z-40 mt-1 w-36 animate-[fadeIn_.12s_ease] overflow-hidden rounded-lg border border-line2 bg-panel2 py-1 shadow-xl">
            {LOCALES.map((l: Locale) => (
              <button
                key={l}
                type="button"
                onClick={() => pick(l)}
                className="flex w-full items-center justify-between px-3 py-2 text-left text-sm text-tx2 transition hover:bg-line hover:text-tx"
              >
                {LOCALE_LABEL[l]}
                {l === locale && <Check size={14} className="text-tx" />}
              </button>
            ))}
          </div>
        </>
      )}
    </div>
  );
}
