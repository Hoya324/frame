"use client";
import dynamic from "next/dynamic";
import { useMemo, useState } from "react";
import { loadCatalogSync } from "@/lib/catalogClient";
import { groupByRegion } from "@/lib/regions";
import { ExhibitionCard } from "@/components/ExhibitionCard";

const MapView = dynamic(() => import("@/components/MapView").then((m) => m.MapView), { ssr: false });

export default function MapPage() {
  const catalog = loadCatalogSync();
  const groups = useMemo(() => groupByRegion(catalog.exhibitions), [catalog.exhibitions]);
  const regions = [...groups.keys()];
  const [region, setRegion] = useState(regions[0] ?? "");
  const items = groups.get(region) ?? [];

  return (
    <main className="mx-auto max-w-[1180px] px-7 py-6">
      <div className="mb-4 flex flex-wrap gap-2">
        {regions.map((r) => (
          <button key={r} onClick={() => setRegion(r)}
            className={`rounded-full px-3.5 py-1.5 text-[13px] ${r === region ? "bg-white font-semibold text-black" : "border border-line text-tx2"}`}>
            {r} <span className="opacity-60">{groups.get(r)?.length}</span>
          </button>
        ))}
      </div>
      <div className="grid gap-5 md:grid-cols-[1fr_360px]">
        <MapView items={items} height={560} />
        <div className="grid grid-cols-2 gap-4 md:grid-cols-1">
          {items.map((e) => <ExhibitionCard key={e.id} exhibition={e} />)}
        </div>
      </div>
    </main>
  );
}
