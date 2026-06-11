"use client";
import Link from "next/link";
import { useMemo } from "react";
import { MasterCard } from "@/components/MasterCard";
import { useLang } from "@/components/LanguageProvider";
import { parseMasters } from "@/lib/masters";
import mastersRaw from "../../../../public/data/masters.json";

export default function PhotographersPage() {
  const { t } = useLang();
  // One flat, chronological wall — entries without a birth year (anthologies) close the list.
  const masters = useMemo(
    () =>
      [...parseMasters(mastersRaw).masters].sort(
        (a, b) => (a.birthYear ?? 9999) - (b.birthYear ?? 9999),
      ),
    [],
  );
  return (
    <main className="mx-auto max-w-[1180px] px-7 py-10">
      <Link href="/masters" className="text-sm text-tx3 hover:text-tx">← {t("curation.title")}</Link>
      <h1 className="mt-6 text-[32px] font-extrabold tracking-tight">{t("masters.title")}</h1>
      <p className="mt-2 text-sm text-tx2">{t("masters.subtitle")}</p>
      <div className="mt-8 grid grid-cols-2 gap-4 md:grid-cols-4">
        {masters.map((m) => <MasterCard key={m.id} m={m} />)}
      </div>
    </main>
  );
}
