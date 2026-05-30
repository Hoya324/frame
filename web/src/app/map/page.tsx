"use client";
import dynamic from "next/dynamic";
import { useMemo, useState } from "react";
import { useRouter } from "next/navigation";
import { loadCatalogSync } from "@/lib/catalogClient";
import { CITY_ORDER, regionBucket, type Country } from "@/lib/regions";
import { ExhibitionCard } from "@/components/ExhibitionCard";
import { FilterChips } from "@/components/FilterChips";

const MapView = dynamic(() => import("@/components/MapView").then((m) => m.MapView), { ssr: false });

const COUNTRY_ORDER: Country[] = ["한국", "일본"];

export default function MapPage() {
  const router = useRouter();
  const catalog = loadCatalogSync();
  const [cities, setCities] = useState<string[]>([]);
  const toggle = (v: string) =>
    setCities((c) => (c.includes(v) ? c.filter((x) => x !== v) : [...c, v]));

  // Only exhibitions with coordinates can plot; tag each with its city bucket.
  const mappable = useMemo(
    () =>
      catalog.exhibitions
        .filter((e) => e.venue?.lat != null && e.venue?.lng != null)
        .map((e) => ({ e, bucket: regionBucket(e.venue?.region) })),
    [catalog.exhibitions],
  );

  const cityGroups = useMemo(() => {
    const present = new Map<Country, Set<string>>();
    for (const { bucket } of mappable) {
      if (!bucket) continue;
      const set = present.get(bucket.country) ?? new Set<string>();
      set.add(bucket.city);
      present.set(bucket.country, set);
    }
    return COUNTRY_ORDER.map((country) => ({
      country,
      cities: CITY_ORDER[country].filter((c) => present.get(country)?.has(c)),
    })).filter((g) => g.cities.length > 0);
  }, [mappable]);

  const items = useMemo(
    () =>
      mappable
        .filter(({ bucket }) => cities.length === 0 || (bucket && cities.includes(bucket.city)))
        .map(({ e }) => e),
    [mappable, cities],
  );

  return (
    <main className="mx-auto max-w-[1180px] px-7 py-6">
      <div className="mb-4 space-y-2">
        {cityGroups.map((g) => (
          <div key={g.country} className="flex items-center gap-2">
            <span className="shrink-0 text-xs text-tx3">{g.country}</span>
            <FilterChips active={cities} onToggle={toggle}
              options={g.cities.map((c) => ({ value: c, label: c }))} />
          </div>
        ))}
      </div>
      <div className="grid gap-5 md:grid-cols-[1fr_360px]">
        <MapView items={items} height={560} onSelect={(id) => router.push(`/exhibitions/${id}`)} />
        <div className="grid max-h-[560px] grid-cols-2 gap-4 overflow-y-auto md:grid-cols-1">
          {items.map((e) => <ExhibitionCard key={e.id} exhibition={e} />)}
        </div>
      </div>
    </main>
  );
}
