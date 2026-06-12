"use client";
import Link from "next/link";
import { useMemo } from "react";
import { CinemaSection } from "@/components/CinemaSection";
import { ContemporaryRail } from "@/components/ContemporaryRail";
import { MasterCard } from "@/components/MasterCard";
import { useLang } from "@/components/LanguageProvider";
import { parseMasters } from "@/lib/masters";
import mastersRaw from "../../../public/data/masters.json";

const PREVIEW_MASTERS = 8;

// Curation hub: a preview of each curation (cinema, photographers, contemporary)
// with a 전체 보기 link to its full page. The full lists live at
// /masters/cinema and /masters/photographers.
export default function MastersHub() {
  const { t } = useLang();
  const masters = useMemo(
    () =>
      [...parseMasters(mastersRaw).masters].sort(
        (a, b) => (a.birthYear ?? 9999) - (b.birthYear ?? 9999),
      ),
    [],
  );
  const preview = masters.slice(0, PREVIEW_MASTERS);

  return (
    <main className="mx-auto max-w-[1180px] px-7 py-10">
      <h1 className="text-[32px] font-extrabold tracking-tight">{t("curation.title")}</h1>
      <p className="mt-2 text-sm text-tx2">{t("curation.subtitle")}</p>

      <div className="mt-9">
        <CinemaSection />
      </div>

      <div className="mt-12">
        <div className="flex items-baseline justify-between gap-4">
          <div>
            <h2 className="text-lg font-bold tracking-tight">{t("masters.title")}</h2>
            <p className="mt-1 text-sm text-tx2">{t("masters.subtitle")}</p>
          </div>
          <Link href="/masters/photographers"
            className="shrink-0 whitespace-nowrap text-[13px] text-tx3 hover:text-tx">
            {t("curation.viewAll")} →
          </Link>
        </div>
        <div className="mt-4 grid grid-cols-2 gap-4 md:grid-cols-4">
          {preview.map((m) => <MasterCard key={m.id} m={m} />)}
        </div>
      </div>

      <div className="mt-12">
        <ContemporaryRail />
      </div>
    </main>
  );
}
