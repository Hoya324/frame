"use client";
import Link from "next/link";
import { useMemo, useState } from "react";
import { Search } from "lucide-react";
import { CinemaCard } from "@/components/CinemaCard";
import { FilterChips } from "@/components/FilterChips";
import { FilterGroup } from "@/components/controls/FilterGroup";
import { useLang } from "@/components/LanguageProvider";
import {
  cinemaEntries, filterCinema, presentDecades, searchCinema, sortCinema,
  type CinemaKind, type CinemaSortKey,
} from "@/lib/cinemaFilter";

const SORTS: CinemaSortKey[] = ["newest", "oldest", "name"];
const SORT_I18N: Record<CinemaSortKey, string> = {
  newest: "cinema.sortNewest", oldest: "cinema.sortOldest", name: "cinema.sortName",
};

export default function CinemaPage() {
  const { t, locale } = useLang();
  const all = useMemo(() => cinemaEntries(), []);
  const decades = useMemo(() => presentDecades(all), [all]);

  const [q, setQ] = useState("");
  const [kinds, setKinds] = useState<CinemaKind[]>([]);
  const [decadeSel, setDecadeSel] = useState<number[]>([]);
  const [sort, setSort] = useState<CinemaSortKey>("newest");

  const toggleKind = (v: string) =>
    setKinds((k) => (k.includes(v as CinemaKind) ? k.filter((x) => x !== v) : [...k, v as CinemaKind]));
  const toggleDecade = (v: string) =>
    setDecadeSel((d) => (d.includes(+v) ? d.filter((x) => x !== +v) : [...d, +v]));

  const results = useMemo(() => {
    const filtered = filterCinema(all, { kinds, decades: decadeSel });
    return sortCinema(searchCinema(filtered, q), sort, locale);
  }, [all, kinds, decadeSel, q, sort, locale]);

  return (
    <main className="mx-auto max-w-[1180px] px-7 py-10">
      <Link href="/masters" className="text-sm text-tx3 hover:text-tx">← {t("curation.title")}</Link>
      <h1 className="mt-5 text-[32px] font-extrabold tracking-tight">{t("cinema.title")}</h1>
      <p className="mt-2 text-sm text-tx2">{t("cinema.subtitle")}</p>
      <p className="mt-3 text-[12px] text-tx3">{t("cinema.modernNote")}</p>

      <div className="mt-6 mb-3 flex items-center gap-2 rounded-lg border border-line px-3 py-2.5">
        <Search size={16} className="text-tx3" />
        <input value={q} onChange={(e) => setQ(e.target.value)} placeholder={t("cinema.searchPlaceholder")}
          className="w-full bg-transparent text-sm outline-none placeholder:text-tx3" />
      </div>

      <div className="mb-3 flex flex-wrap items-center gap-x-3 gap-y-2">
        <FilterGroup label={t("cinema.kindLabel")}>
          <FilterChips active={kinds} onToggle={toggleKind} options={[
            { value: "modern", label: t("cinema.kindModern") },
            { value: "pd", label: t("cinema.kindPd") },
          ]} />
        </FilterGroup>
        <span className="h-4 w-px bg-line2" aria-hidden="true" />
        <FilterGroup label={t("controls.sort")}>
          <FilterChips active={[sort]} onToggle={(v) => setSort(v as CinemaSortKey)}
            options={SORTS.map((k) => ({ value: k, label: t(SORT_I18N[k]) }))} />
        </FilterGroup>
      </div>

      {decades.length > 1 && (
        <div className="mb-3 flex items-center gap-2">
          <span className="shrink-0 text-[11px] text-tx3">{t("cinema.decadeLabel")}</span>
          <FilterChips active={decadeSel.map(String)} onToggle={toggleDecade}
            options={decades.map((d) => ({ value: String(d), label: `${d}s` }))} />
        </div>
      )}

      <div className="mb-4 text-sm text-tx3">{t("cinema.count").replace("{n}", String(results.length))}</div>

      {results.length === 0 ? (
        <div className="py-20 text-center text-tx3">{t("cinema.empty")}</div>
      ) : (
        <div className="grid grid-cols-2 gap-4 md:grid-cols-4">
          {results.map((e) => <CinemaCard key={e.scene.id} scene={e.scene} />)}
        </div>
      )}
    </main>
  );
}
