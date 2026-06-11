"use client";
import Link from "next/link";
import { useLang } from "@/components/LanguageProvider";
import { CINEMA_MODERN, CINEMA_PD, type CinemaScene } from "@/lib/cinema";
import type { Locale } from "@/lib/i18n";

// "영화, 한 프레임" — learn composition, light and colour from cinema. Modern
// colour cinema leads; public-domain early frames follow. Each card opens a
// detail page (/masters/cinema/[id]) with more stills and a longer curation.
// Modern films are in-copyright, shown as 인용 with a © studio credit.
export function CinemaSection({ variant = "full" }: { variant?: "preview" | "full" }) {
  const { t, locale } = useLang();
  const modern = CINEMA_MODERN.filter((s) => s.image);

  if (variant === "preview") {
    const preview = [...modern.slice(0, 3), ...CINEMA_PD.slice(0, 1)];
    return (
      <section aria-label={t("cinema.title")}>
        <SectionHead title={t("cinema.title")} subtitle={t("cinema.subtitle")}
          href="/masters/cinema" viewAll={t("curation.viewAll")} />
        <div className="mt-4 grid grid-cols-2 gap-4 md:grid-cols-4">
          {preview.map((s) => <FrameCard key={s.id} s={s} locale={locale} />)}
        </div>
      </section>
    );
  }

  return (
    <section aria-label={t("cinema.title")}>
      <h2 className="text-lg font-bold tracking-tight">{t("cinema.title")}</h2>
      <p className="mt-1 text-sm text-tx2">{t("cinema.subtitle")}</p>

      <div className="mb-4 mt-7 flex flex-wrap items-baseline justify-between gap-x-4">
        <h3 className="text-[13px] font-semibold uppercase tracking-wide text-tx3">
          {t("cinema.modernLabel")}
        </h3>
        <span className="text-[12px] text-tx3">{t("cinema.modernNote")}</span>
      </div>
      <div className="grid grid-cols-2 gap-4 md:grid-cols-4">
        {modern.map((s) => <FrameCard key={s.id} s={s} locale={locale} />)}
      </div>

      <h3 className="mb-4 mt-10 text-[13px] font-semibold uppercase tracking-wide text-tx3">
        {t("cinema.pdLabel")}
      </h3>
      <div className="grid grid-cols-2 gap-4 md:grid-cols-4">
        {CINEMA_PD.map((s) => <FrameCard key={s.id} s={s} locale={locale} />)}
      </div>
    </section>
  );
}

function SectionHead({ title, subtitle, href, viewAll }: {
  title: string; subtitle: string; href: string; viewAll: string;
}) {
  return (
    <div className="flex items-baseline justify-between gap-4">
      <div>
        <h2 className="text-lg font-bold tracking-tight">{title}</h2>
        <p className="mt-1 text-sm text-tx2">{subtitle}</p>
      </div>
      <Link href={href} className="shrink-0 whitespace-nowrap text-[13px] text-tx3 hover:text-tx">
        {viewAll} →
      </Link>
    </div>
  );
}

function FrameCard({ s, locale }: { s: CinemaScene; locale: Locale }) {
  return (
    <Link
      href={`/masters/cinema/${s.id}`}
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
    </Link>
  );
}
