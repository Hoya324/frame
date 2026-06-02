"use client";
import { useMemo, useState } from "react";
import { loadCatalogSync } from "@/lib/catalogClient";
import { useAuth, useBookmarks } from "@/components/AuthProvider";
import { ExhibitionCard } from "@/components/ExhibitionCard";
import { useLang } from "@/components/LanguageProvider";
import { applyFilters, type FilterState } from "@/lib/filters";
import { sortExhibitions, type SortKey } from "@/lib/sort";
import { FilterChips } from "@/components/FilterChips";
import { FilterGroup } from "@/components/controls/FilterGroup";
import { SortChips } from "@/components/controls/SortChips";

export default function ScrapPage() {
  const catalog = loadCatalogSync();
  const { user, loading, signIn } = useAuth();
  const { ids } = useBookmarks();
  const { t } = useLang();
  const today = new Date();

  const [statuses, setStatuses] = useState<string[]>([]);
  const [sort, setSort] = useState<SortKey>("closing");
  const toggleStatus = (v: string) =>
    setStatuses((s) => (s.includes(v) ? s.filter((x) => x !== v) : [...s, v]));

  const saved = useMemo(() => {
    const base = catalog.exhibitions.filter((e) => ids.has(e.id));
    const f: FilterState = {
      statuses: statuses as FilterState["statuses"], mediums: [], types: [], freeOnly: false, regions: [],
    };
    return sortExhibitions(applyFilters(base, f), sort, { today });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [catalog.exhibitions, ids, statuses, sort]);

  if (loading) return <main className="mx-auto max-w-[1180px] px-7 py-16 text-tx3">{t("common.loading")}</main>;
  if (!user) {
    return (
      <main className="mx-auto max-w-[1180px] px-7 py-20 text-center">
        <h1 className="text-2xl font-extrabold tracking-tight">{t("scrap.title")}</h1>
        <p className="mt-3 text-tx2">{t("scrap.loginPrompt")}</p>
        <button
          onClick={() => void signIn()}
          className="mt-6 rounded-md bg-white px-5 py-2.5 text-sm font-semibold text-black"
        >
          {t("common.signInGoogle")}
        </button>
      </main>
    );
  }
  return (
    <main className="mx-auto max-w-[1180px] px-7 py-8">
      <h1 className="text-[28px] font-extrabold tracking-tight">{t("scrap.title")}</h1>
      <p className="mt-2 text-sm text-tx3">{t("scrap.subtitle").replace("{n}", String(saved.length))}</p>
      <div className="mt-5 flex flex-wrap items-center gap-x-3 gap-y-2">
        <FilterGroup label={t("controls.status")}>
          <FilterChips active={statuses} onToggle={toggleStatus} options={[
            { value: "ongoing", label: t("filter.ongoing") },
            { value: "upcoming", label: t("filter.upcoming") },
            { value: "past", label: t("filter.past") },
          ]} />
        </FilterGroup>
        <span className="h-4 w-px bg-line2" aria-hidden="true" />
        <FilterGroup label={t("controls.sort")}>
          <SortChips value={sort} options={["recommended", "closing", "recent"]} onChange={setSort} />
        </FilterGroup>
      </div>
      {saved.length === 0 ? (
        <div className="py-20 text-center text-tx3">{t("scrap.empty")}</div>
      ) : (
        <div className="mt-6 grid grid-cols-2 gap-4 md:grid-cols-4">
          {saved.map((e) => (
            <ExhibitionCard key={e.id} exhibition={e} today={today} />
          ))}
        </div>
      )}
    </main>
  );
}
