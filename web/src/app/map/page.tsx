"use client";
import dynamic from "next/dynamic";
import { useMemo, useState } from "react";
import { useRouter } from "next/navigation";
import { MapPin, Loader2 } from "lucide-react";
import { loadCatalogSync } from "@/lib/catalogClient";
import { CITY_ORDER, regionBucket, type Country } from "@/lib/regions";
import { ExhibitionCard } from "@/components/ExhibitionCard";
import { FilterChips } from "@/components/FilterChips";
import { VenueSheet } from "@/components/VenueSheet";
import { useLang } from "@/components/LanguageProvider";

const MapView = dynamic(() => import("@/components/MapView").then((m) => m.MapView), { ssr: false });

const COUNTRY_ORDER: Country[] = ["한국", "일본"];

function distanceKm(a: [number, number], b: [number, number]): number {
  const R = 6371;
  const toRad = (d: number) => (d * Math.PI) / 180;
  const dLat = toRad(b[1] - a[1]);
  const dLng = toRad(b[0] - a[0]);
  const s =
    Math.sin(dLat / 2) ** 2 +
    Math.cos(toRad(a[1])) * Math.cos(toRad(b[1])) * Math.sin(dLng / 2) ** 2;
  return 2 * R * Math.asin(Math.sqrt(s));
}

export default function MapPage() {
  const router = useRouter();
  const catalog = loadCatalogSync();
  const { t } = useLang();
  const [cities, setCities] = useState<string[]>([]);
  const [visibleIds, setVisibleIds] = useState<Set<string> | null>(null);
  const [sheetVenueId, setSheetVenueId] = useState<string | null>(null);
  const [userLoc, setUserLoc] = useState<[number, number] | null>(null);
  const [locState, setLocState] = useState<"idle" | "locating" | "error">("idle");
  const toggle = (v: string) => {
    setCities((c) => (c.includes(v) ? c.filter((x) => x !== v) : [...c, v]));
  };

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

  // The sidebar mirrors what is currently on screen, so the list count always
  // matches the markers the user can see. Clicking a multi-exhibition venue
  // marker pins the list to that venue. When located, sort by proximity.
  const listed = useMemo(() => {
    const base = visibleIds ? items.filter((e) => visibleIds.has(e.id)) : items;
    if (!userLoc) return base;
    return [...base].sort((a, b) => {
      const da = distanceKm(userLoc, [a.venue!.lng!, a.venue!.lat!]);
      const db = distanceKm(userLoc, [b.venue!.lng!, b.venue!.lat!]);
      return da - db;
    });
  }, [items, visibleIds, userLoc]);

  const sheet = useMemo(() => {
    if (!sheetVenueId) return null;
    const exhibitions = items.filter((e) => e.venue?.id === sheetVenueId);
    const venueMeta = exhibitions[0]?.venue ?? null;
    if (!venueMeta) return null;
    return { venue: venueMeta, exhibitions };
  }, [items, sheetVenueId]);

  const locate = () => {
    if (!("geolocation" in navigator)) {
      setLocState("error");
      return;
    }
    setLocState("locating");
    navigator.geolocation.getCurrentPosition(
      (pos) => {
        setUserLoc([pos.coords.longitude, pos.coords.latitude]);
        setLocState("idle");
      },
      () => setLocState("error"),
      { enableHighAccuracy: true, timeout: 10000 },
    );
  };

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

      <div className="mb-3 flex flex-wrap items-center gap-3">
        <button
          type="button"
          onClick={locate}
          disabled={locState === "locating"}
          className="flex items-center gap-1.5 rounded-full border border-line2 bg-white px-4 py-1.5 text-sm font-semibold text-black transition active:scale-95 disabled:opacity-60"
        >
          {locState === "locating"
            ? <Loader2 size={15} className="animate-spin" />
            : <MapPin size={15} />}
          {locState === "locating" ? t("map.locating") : t("map.nearby")}
        </button>
        {locState === "error" && <span className="text-sm text-rose-400">{t("map.locateError")}</span>}
        {userLoc && locState === "idle" && (
          <span className="rounded-full border border-line px-3 py-1 text-xs text-tx2">{t("map.nearbyOn")}</span>
        )}
        <span className="ml-auto text-xs text-tx3">{t("map.showing")} <b className="text-tx2">{listed.length}</b></span>
      </div>

      <div className="grid gap-5 md:grid-cols-[1fr_360px]">
        <MapView
          items={items}
          height={560}
          userLocation={userLoc}
          selectedVenueId={sheetVenueId}
          onViewChange={(ids) => setVisibleIds(new Set(ids))}
          onVenueSelect={(id) => setSheetVenueId(id)}
          onSelect={(id) => router.push(`/exhibitions/${id}`)}
        />
        <div className="grid max-h-[560px] grid-cols-2 gap-4 overflow-y-auto md:grid-cols-1">
          {listed.map((e) => <ExhibitionCard key={e.id} exhibition={e} />)}
        </div>
      </div>
      {sheet && (
        <VenueSheet
          venue={sheet.venue}
          exhibitions={sheet.exhibitions}
          onClose={() => setSheetVenueId(null)}
        />
      )}
    </main>
  );
}
