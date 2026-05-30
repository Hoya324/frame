"use client";
import { useMemo, useState } from "react";
import { Search } from "lucide-react";
import { loadCatalogSync } from "@/lib/catalogClient";
import { applyFilters, searchExhibitions, type FilterState } from "@/lib/filters";
import { CITY_ORDER, regionBucket, type Country } from "@/lib/regions";
import { ExhibitionCard } from "@/components/ExhibitionCard";
import { FilterChips } from "@/components/FilterChips";

const COUNTRY_ORDER: Country[] = ["한국", "일본"];

export default function SearchPage() {
  const catalog = loadCatalogSync();
  const [q, setQ] = useState("");
  const [chips, setChips] = useState<string[]>([]);
  const toggle = (v: string) => setChips((c) => (c.includes(v) ? c.filter((x) => x !== v) : [...c, v]));

  // Collapse raw venue regions to coarse city buckets, then list only the
  // buckets that actually have exhibitions — in stable CITY_ORDER per country.
  const cityGroups = useMemo(() => {
    const present = new Map<Country, Set<string>>();
    for (const v of catalog.venues) {
      const b = regionBucket(v.region);
      if (!b) continue;
      const set = present.get(b.country) ?? new Set<string>();
      set.add(b.city);
      present.set(b.country, set);
    }
    return COUNTRY_ORDER.map((country) => ({
      country,
      cities: CITY_ORDER[country].filter((c) => present.get(country)?.has(c)),
    })).filter((g) => g.cities.length > 0);
  }, [catalog.venues]);

  const allCities = useMemo(
    () => new Set(cityGroups.flatMap((g) => g.cities)),
    [cityGroups],
  );

  const f: FilterState = {
    statuses: chips.filter((c) => ["ongoing", "upcoming", "past"].includes(c)) as FilterState["statuses"],
    mediums: chips.filter((c) => ["photo", "video", "gear"].includes(c)),
    types: chips.filter((c) => ["solo", "group", "curated"].includes(c)),
    freeOnly: chips.includes("free"),
    regions: chips.filter((c) => allCities.has(c)),
  };
  const results = searchExhibitions(applyFilters(catalog.exhibitions, f), q);

  return (
    <main className="mx-auto max-w-[1180px] px-7 py-8">
      <div className="mb-5 flex items-center gap-2 rounded-lg border border-line px-3 py-2.5">
        <Search size={16} className="text-tx3" />
        <input value={q} onChange={(e) => setQ(e.target.value)} placeholder="전시 · 작가 · 장소"
          className="w-full bg-transparent text-sm outline-none placeholder:text-tx3" />
      </div>
      <div className="mb-3"><FilterChips active={chips} onToggle={toggle} options={[
        { value: "ongoing", label: "진행중" }, { value: "upcoming", label: "예정" }, { value: "past", label: "종료" },
        { value: "photo", label: "사진" }, { value: "video", label: "영상" }, { value: "gear", label: "장비" },
        { value: "solo", label: "개인전" }, { value: "group", label: "단체전" }, { value: "free", label: "무료" },
      ]} /></div>
      {cityGroups.map((g) => (
        <div key={g.country} className="mb-3 flex items-center gap-2">
          <span className="shrink-0 text-xs text-tx3">{g.country}</span>
          <FilterChips active={chips} onToggle={toggle}
            options={g.cities.map((c) => ({ value: c, label: c }))} />
        </div>
      ))}
      <div className="mb-4 text-sm text-tx3">{results.length}건</div>
      {results.length === 0 ? (
        <div className="py-20 text-center text-tx3">조건에 맞는 전시가 없어요</div>
      ) : (
        <div className="grid grid-cols-2 gap-4 md:grid-cols-4">
          {results.map((e) => <ExhibitionCard key={e.id} exhibition={e} />)}
        </div>
      )}
    </main>
  );
}
