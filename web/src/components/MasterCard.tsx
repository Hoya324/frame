"use client";
import Link from "next/link";
import { PosterImage } from "@/components/PosterImage";
import { useLang } from "@/components/LanguageProvider";
import { inLocale } from "@/lib/catalog";
import { masterFaceImage, type Master } from "@/lib/masters";

export function MasterCard({ m }: { m: Master }) {
  const { t, locale } = useLang();
  const name = inLocale(m.name, m.tr, locale, "name");
  const tagline = inLocale(m.tagline, m.tr, locale, "tagline");
  const years = m.birthYear
    ? t("masters.years", { birth: m.birthYear, death: m.deathYear ?? "" })
    : "";
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
