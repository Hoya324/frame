"use client";
import { useMemo, useState } from "react";
import { Search } from "lucide-react";
import { loadCatalogSync } from "@/lib/catalogClient";
import { applyFilters, searchExhibitions, type FilterState } from "@/lib/filters";
import { ExhibitionCard } from "@/components/ExhibitionCard";
import { FilterChips } from "@/components/FilterChips";

export default function SearchPage() {
  const catalog = loadCatalogSync();
  const [q, setQ] = useState("");
  const [chips, setChips] = useState<string[]>([]);
  const toggle = (v: string) => setChips((c) => (c.includes(v) ? c.filter((x) => x !== v) : [...c, v]));

  const regions = useMemo(
    () => Array.from(new Set(catalog.venues.map((v) => v.region).filter(Boolean))) as string[],
    [catalog.venues],
  );

  const f: FilterState = {
    statuses: chips.filter((c) => ["ongoing", "upcoming", "past"].includes(c)) as FilterState["statuses"],
    mediums: chips.filter((c) => ["photo", "video", "gear"].includes(c)),
    types: chips.filter((c) => ["solo", "group", "curated"].includes(c)),
    freeOnly: chips.includes("free"),
    regions: chips.filter((c) => regions.includes(c)),
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
        ...regions.map((r) => ({ value: r, label: r })),
      ]} /></div>
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
