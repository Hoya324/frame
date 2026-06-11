"use client";
import { useLang } from "@/components/LanguageProvider";
import { CONTEMPORARY, type ContemporaryMaster } from "@/lib/contemporary";
import type { Locale } from "@/lib/i18n";

// Slow, continuously scrolling rail of contemporary masters. Their works are
// still in copyright, so the cards are typographic and link out. The track
// holds two identical copies and slides -50% for a seamless loop; card width
// is fixed, so the viewport naturally shows ~3 on phones up to ~6 on desktop.
export function ContemporaryRail() {
  const { t, locale } = useLang();
  return (
    <section className="pt-9" aria-label={t("masters.nowTitle")}>
      <div className="flex flex-wrap items-baseline justify-between gap-x-4">
        <h2 className="text-lg font-bold tracking-tight">{t("masters.nowTitle")}</h2>
        <span className="text-[12px] text-tx3">{t("masters.nowHint")}</span>
      </div>
      <div className="group relative mt-4 overflow-hidden">
        <div className="masters-marquee flex w-max group-hover:[animation-play-state:paused]">
          {[0, 1].map((copy) => (
            <div key={copy} aria-hidden={copy === 1} className="flex gap-3 pr-3">
              {CONTEMPORARY.map((m) => (
                <RailCard key={`${copy}-${m.id}`} m={m} locale={locale} t={t} tabbable={copy === 0} />
              ))}
            </div>
          ))}
        </div>
        <div className="pointer-events-none absolute inset-y-0 left-0 w-10 bg-gradient-to-r from-bg to-transparent" />
        <div className="pointer-events-none absolute inset-y-0 right-0 w-10 bg-gradient-to-l from-bg to-transparent" />
      </div>
    </section>
  );
}

function RailCard({ m, locale, t, tabbable }: {
  m: ContemporaryMaster; locale: Locale;
  t: (k: string, v?: Record<string, string | number>) => string;
  tabbable: boolean;
}) {
  return (
    <a
      href={m.url}
      target="_blank"
      rel="noopener noreferrer"
      tabIndex={tabbable ? 0 : -1}
      className="flex w-[180px] shrink-0 flex-col justify-between rounded border border-line bg-panel p-4 transition-colors hover:border-line2 sm:w-[200px]"
    >
      <div>
        <div className="font-semibold tracking-tight">{m.name[locale]}</div>
        <div className="mt-0.5 text-[12px] text-tx3">{m.years}</div>
        <p className="mt-2 line-clamp-3 text-[13px] leading-snug text-tx2">{m.line[locale]}</p>
      </div>
      <div className="mt-3 text-[12px] text-tx3">{t("masters.nowVisit")} ↗</div>
    </a>
  );
}
