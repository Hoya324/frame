"use client";
import { useLang } from "@/components/LanguageProvider";
import { CINEMA_MODERN, CINEMA_PD, type CinemaScene } from "@/lib/cinema";
import type { Locale } from "@/lib/i18n";

// "영화, 한 프레임" — placed above the masters grid. Public-domain scenes show
// the real frame; in-copyright modern films appear (once a still is sourced)
// as a 인용 with © studio attribution. Both link out.
export function CinemaSection() {
  const { t, locale } = useLang();
  // In-copyright modern stills are included only once a low-res still has been
  // sourced; until then the entry has no `image` and is hidden rather than
  // rendered as a broken card.
  const modern = CINEMA_MODERN.filter((s) => s.image);
  return (
    <section className="pt-2" aria-label={t("cinema.title")}>
      <h2 className="text-lg font-bold tracking-tight">{t("cinema.title")}</h2>
      <p className="mt-1 text-sm text-tx2">{t("cinema.subtitle")}</p>

      <h3 className="mb-4 mt-7 text-[13px] font-semibold uppercase tracking-wide text-tx3">
        {t("cinema.pdLabel")}
      </h3>
      <div className="grid grid-cols-2 gap-4 md:grid-cols-4">
        {CINEMA_PD.map((s) => <FrameCard key={s.id} s={s} locale={locale} />)}
      </div>

      {modern.length > 0 && (
        <>
          <div className="mb-4 mt-9 flex flex-wrap items-baseline justify-between gap-x-4">
            <h3 className="text-[13px] font-semibold uppercase tracking-wide text-tx3">
              {t("cinema.modernLabel")}
            </h3>
            <span className="text-[12px] text-tx3">{t("cinema.modernNote")}</span>
          </div>
          <div className="grid grid-cols-2 gap-4 md:grid-cols-3">
            {modern.map((s) => <FrameCard key={s.id} s={s} locale={locale} />)}
          </div>
        </>
      )}
    </section>
  );
}

function FrameCard({ s, locale }: { s: CinemaScene; locale: Locale }) {
  return (
    <a
      href={s.url}
      target="_blank"
      rel="noopener noreferrer"
      className="group block overflow-hidden rounded border border-line transition-colors hover:border-line2"
    >
      <div className="relative aspect-[4/3] bg-panel2">
        {/* eslint-disable-next-line @next/next/no-img-element */}
        <img src={s.image} alt={s.title[locale]} loading="lazy" className="h-full w-full object-cover" />
      </div>
      <div className="p-3">
        <div className="font-semibold tracking-tight">{s.title[locale]}</div>
        <div className="text-[12px] text-tx3">{s.credit[locale]}</div>
        <p className="mt-1 line-clamp-3 text-[13px] leading-snug text-tx2">{s.lesson[locale]}</p>
        {s.studio && <div className="mt-2 text-[11px] text-tx3">© {s.studio}</div>}
      </div>
    </a>
  );
}
