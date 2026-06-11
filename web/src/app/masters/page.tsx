"use client";
import Link from "next/link";
import { useMemo } from "react";
import { PosterImage } from "@/components/PosterImage";
import { useLang } from "@/components/LanguageProvider";
import { inLocale } from "@/lib/catalog";
import type { Locale } from "@/lib/i18n";
import { parseMasters, masterFaceImage, type Master } from "@/lib/masters";
import mastersRaw from "../../../public/data/masters.json";

export default function MastersPage() {
  const { t, locale } = useLang();
  // One flat, chronological wall — no country/region grouping. Entries
  // without a birth year (anthologies) close the list.
  const masters = useMemo(
    () =>
      [...parseMasters(mastersRaw).masters].sort(
        (a, b) => (a.birthYear ?? 9999) - (b.birthYear ?? 9999),
      ),
    [],
  );

  return (
    <main className="mx-auto max-w-[1180px] px-7 py-10">
      <h1 className="text-[32px] font-extrabold tracking-tight">{t("masters.title")}</h1>
      <p className="mt-2 text-sm text-tx2">{t("masters.subtitle")}</p>

      <div className="grid grid-cols-2 gap-4 pt-9 md:grid-cols-4">
        {masters.map((m) => <MasterCard key={m.id} m={m} locale={locale} t={t} />)}
      </div>
    </main>
  );
}

function MasterCard({ m, locale, t }: {
  m: Master; locale: Locale; t: (k: string, v?: Record<string, string | number>) => string;
}) {
  const name = inLocale(m.name, m.tr, locale, "name");
  const tagline = inLocale(m.tagline, m.tr, locale, "tagline");
  const years = m.birthYear ? t("masters.years", { birth: m.birthYear, death: m.deathYear ?? "" }) : "";
  return (
    <Link href={`/masters/${m.id}`} className="group block overflow-hidden rounded border border-line">
      <div className="relative aspect-[3/4]">
        <PosterImage src={masterFaceImage(m)} alt={name} />
      </div>
      <div className="p-3">
        <div className="font-semibold tracking-tight">{name}</div>
        {years && <div className="text-[12px] text-tx3">{years}</div>}
        {tagline && <div className="mt-1 line-clamp-2 text-[13px] text-tx2">{tagline}</div>}
      </div>
    </Link>
  );
}
