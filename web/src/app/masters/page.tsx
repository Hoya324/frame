"use client";
import Link from "next/link";
import { useMemo } from "react";
import { PosterImage } from "@/components/PosterImage";
import { useLang } from "@/components/LanguageProvider";
import { inLocale } from "@/lib/catalog";
import type { Locale } from "@/lib/i18n";
import { parseMasters, masterFaceImage, type Master, type Region } from "@/lib/masters";
import mastersRaw from "../../../public/data/masters.json";

const REGION_ORDER: Region[] = ["kr", "jp", "modern", "foreign"];
const REGION_KEY: Record<Region, string> = {
  kr: "masters.regionKr", jp: "masters.regionJp",
  modern: "masters.regionModern", foreign: "masters.regionForeign",
};

export default function MastersPage() {
  const { t, locale } = useLang();
  const masters = useMemo(() => parseMasters(mastersRaw).masters, []);
  const byRegion = (r: Region) => masters.filter((m) => m.region === r);

  return (
    <main className="mx-auto max-w-[1180px] px-7 py-10">
      <h1 className="text-[32px] font-extrabold tracking-tight">{t("masters.title")}</h1>
      <p className="mt-2 text-sm text-tx2">{t("masters.subtitle")}</p>

      {REGION_ORDER.map((r) => {
        const items = byRegion(r);
        if (items.length === 0) return null;
        return (
          <section key={r} className="pt-9">
            <h2 className="mb-4 text-lg font-bold tracking-tight">{t(REGION_KEY[r])}</h2>
            <div className="grid grid-cols-2 gap-4 md:grid-cols-4">
              {items.map((m) => <MasterCard key={m.id} m={m} locale={locale} t={t} />)}
            </div>
          </section>
        );
      })}
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
