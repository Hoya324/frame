"use client";
import Link from "next/link";
import { useLang } from "@/components/LanguageProvider";
import { CinemaCard } from "@/components/CinemaCard";
import { CINEMA_MODERN, CINEMA_PD } from "@/lib/cinema";

// Hub preview of "영화, 한 프레임": a few mixed cards + a 전체 보기 link. The full
// searchable/sortable/filterable list lives on /masters/cinema.
export function CinemaSection() {
  const { t } = useLang();
  const modern = CINEMA_MODERN.filter((s) => s.image);
  const preview = [...modern.slice(0, 3), ...CINEMA_PD.slice(0, 1)];
  return (
    <section aria-label={t("cinema.title")}>
      <div className="flex items-baseline justify-between gap-4">
        <div>
          <h2 className="text-lg font-bold tracking-tight">{t("cinema.title")}</h2>
          <p className="mt-1 text-sm text-tx2">{t("cinema.subtitle")}</p>
        </div>
        <Link href="/masters/cinema"
          className="shrink-0 whitespace-nowrap text-[13px] text-tx3 hover:text-tx">
          {t("curation.viewAll")} →
        </Link>
      </div>
      <div className="mt-4 grid grid-cols-2 gap-4 md:grid-cols-4">
        {preview.map((s) => <CinemaCard key={s.id} scene={s} />)}
      </div>
    </section>
  );
}
