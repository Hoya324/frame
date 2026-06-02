"use client";
import { useEffect, useRef } from "react";
import maplibregl, { type StyleSpecification, type GeoJSONSource } from "maplibre-gl";
import "maplibre-gl/dist/maplibre-gl.css";
import type { Exhibition } from "@/lib/catalog";

// CARTO Dark Matter raster basemap — free, key-less, and minimal enough to
// match the app's black theme. Attribution is required and rendered by the map.
const STYLE: StyleSpecification = {
  version: 8,
  sources: {
    carto: {
      type: "raster",
      tiles: [
        "https://a.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}@2x.png",
        "https://b.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}@2x.png",
        "https://c.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}@2x.png",
        "https://d.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}@2x.png",
      ],
      tileSize: 256,
      attribution:
        '© <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> © <a href="https://carto.com/attributions">CARTO</a>',
    },
  },
  layers: [{ id: "carto", type: "raster", source: "carto" }],
};

const SEOUL: [number, number] = [126.98, 37.57];

// Aggregate exhibitions into one feature per venue. Many venues host dozens of
// exhibitions at the exact same coordinate (e.g. 캐논 갤러리 has 100+); plotting
// each as its own point produces clusters that can never expand on zoom because
// the members are coincident. One marker per venue keeps clusters separable and
// lets the marker show a count badge for multi-exhibition venues.
function toFeatureCollection(items: Exhibition[]): GeoJSON.FeatureCollection<GeoJSON.Point> {
  const byVenue = new Map<string, {
    lng: number; lat: number; count: number; poster: string; venueName: string; firstId: string;
  }>();
  for (const e of items) {
    const { lat, lng } = e.venue ?? {};
    if (lat == null || lng == null) continue;
    const key = e.venue?.id ?? `${lng},${lat}`;
    const agg = byVenue.get(key);
    if (agg) {
      agg.count += 1;
      if (!agg.poster && e.posterImageUrl) agg.poster = e.posterImageUrl;
    } else {
      byVenue.set(key, {
        lng, lat, count: 1, poster: e.posterImageUrl ?? "",
        venueName: e.venue?.name ?? "", firstId: e.id,
      });
    }
  }
  const features: GeoJSON.Feature<GeoJSON.Point>[] = [];
  for (const [venueId, v] of byVenue) {
    features.push({
      type: "Feature",
      geometry: { type: "Point", coordinates: [v.lng, v.lat] },
      properties: { venueId, venueName: v.venueName, count: v.count, poster: v.poster, firstId: v.firstId },
    });
  }
  return { type: "FeatureCollection", features };
}

// A small rounded poster thumbnail used as the DOM marker for a venue. Venues
// with more than one exhibition get a count badge.
function posterMarkerEl(p: Record<string, unknown>, onClick: () => void): HTMLElement {
  const el = document.createElement("button");
  el.type = "button";
  el.className = "frame-poster-marker";
  el.title = String(p.venueName ?? "");
  const poster = String(p.poster ?? "");
  if (poster) el.style.backgroundImage = `url("${poster.replace(/"/g, "%22")}")`;
  const count = Number(p.count ?? 1);
  if (count > 1) {
    el.classList.add("frame-poster-marker--stacked");
    const badge = document.createElement("span");
    badge.className = "frame-marker-badge";
    badge.textContent = count > 99 ? "99+" : String(count);
    el.appendChild(badge);
  }
  el.addEventListener("click", (e) => {
    e.stopPropagation();
    onClick();
  });
  return el;
}

export function MapView({ items, height = 480, onSelect, onVenueSelect, onViewChange, userLocation, selectedVenueId }: {
  items: Exhibition[];
  height?: number;
  onSelect?: (id: string) => void;
  onVenueSelect?: (venueId: string) => void;
  onViewChange?: (visibleIds: string[]) => void;
  userLocation?: [number, number] | null;
  selectedVenueId?: string | null;
}) {
  const ref = useRef<HTMLDivElement>(null);
  const mapRef = useRef<maplibregl.Map | null>(null);
  const markerEls = useRef<Record<string, HTMLElement>>({});
  const selectedVenueRef = useRef<string | null>(selectedVenueId ?? null);
  useEffect(() => { selectedVenueRef.current = selectedVenueId ?? null; }, [selectedVenueId]);
  // Keep latest callbacks without re-initializing the map on every render.
  const onSelectRef = useRef(onSelect);
  const onVenueSelectRef = useRef(onVenueSelect);
  const onViewChangeRef = useRef(onViewChange);
  const itemsRef = useRef(items);
  useEffect(() => { onSelectRef.current = onSelect; }, [onSelect]);
  useEffect(() => { onVenueSelectRef.current = onVenueSelect; }, [onVenueSelect]);
  useEffect(() => { onViewChangeRef.current = onViewChange; }, [onViewChange]);
  useEffect(() => { itemsRef.current = items; }, [items]);

  useEffect(() => {
    if (!ref.current) return;
    const data = toFeatureCollection(items);
    const pts = data.features;

    const map = new maplibregl.Map({
      container: ref.current,
      style: STYLE,
      center: pts[0] ? (pts[0].geometry.coordinates as [number, number]) : SEOUL,
      zoom: 10,
      attributionControl: { compact: true },
    });
    mapRef.current = map;
    map.addControl(new maplibregl.NavigationControl({ showCompass: false }), "top-right");

    // DOM markers for individual (non-clustered) points, synced to the viewport.
    const markers: Record<string, maplibregl.Marker> = {};
    let onScreen: Record<string, maplibregl.Marker> = {};
    const syncMarkers = () => {
      if (!map.getSource("exhibitions") || !map.isSourceLoaded("exhibitions")) return;
      const features = map.querySourceFeatures("exhibitions");
      const next: Record<string, maplibregl.Marker> = {};
      for (const f of features) {
        const p = f.properties ?? {};
        if (p.point_count) continue; // clusters keep the native circle layer
        const venueId = p.venueId as string | undefined;
        if (!venueId || next[venueId]) continue;
        const coords = (f.geometry as GeoJSON.Point).coordinates as [number, number];
        let marker = markers[venueId];
        if (!marker) {
          // 단일 전시 venue → 바로 상세로; 멀티 → 공간 시트 오픈.
          const el = posterMarkerEl(p, () => {
            if (Number(p.count ?? 1) > 1) onVenueSelectRef.current?.(venueId);
            else onSelectRef.current?.(String(p.firstId));
          });
          if (venueId === selectedVenueRef.current) el.classList.add("frame-poster-marker--selected");
          markerEls.current[venueId] = el;
          marker = markers[venueId] = new maplibregl.Marker({ element: el }).setLngLat(coords);
        }
        next[venueId] = marker;
        if (!onScreen[venueId]) marker.addTo(map);
      }
      for (const id in onScreen) if (!next[id]) onScreen[id].remove();
      onScreen = next;
    };

    const reportView = () => {
      const cb = onViewChangeRef.current;
      if (!cb) return;
      const b = map.getBounds();
      const ids: string[] = [];
      for (const e of itemsRef.current) {
        const { lat, lng } = e.venue ?? {};
        if (lat == null || lng == null) continue;
        if (b.contains([lng, lat])) ids.push(e.id);
      }
      cb(ids);
    };

    map.on("load", () => {
      map.addSource("exhibitions", {
        type: "geojson",
        data,
        cluster: true,
        clusterRadius: 48,
        clusterMaxZoom: 14,
        // Each feature is one venue carrying its own exhibition `count`; sum them
        // so the cluster badge reflects the number of EXHIBITIONS in the area,
        // not the number of venues (a single venue can host 100+ shows).
        clusterProperties: { exhibitions: ["+", ["coalesce", ["get", "count"], 1]] },
      });

      map.addLayer({
        id: "clusters",
        type: "circle",
        source: "exhibitions",
        filter: ["has", "point_count"],
        paint: {
          "circle-color": "#ffffff",
          "circle-opacity": 0.92,
          "circle-radius": ["step", ["get", "exhibitions"], 16, 25, 21, 100, 27],
          "circle-stroke-width": 4,
          "circle-stroke-color": "rgba(255,255,255,0.18)",
        },
      });
      map.addLayer({
        id: "cluster-count",
        type: "symbol",
        source: "exhibitions",
        filter: ["has", "point_count"],
        layout: {
          "text-field": [
            "case",
            [">", ["get", "exhibitions"], 999], "999+",
            ["to-string", ["get", "exhibitions"]],
          ],
          "text-font": ["Open Sans Bold", "Arial Unicode MS Bold"],
          "text-size": 13,
        },
        paint: { "text-color": "#000000" },
      });

      if (pts.length > 1) {
        const bounds = new maplibregl.LngLatBounds();
        for (const f of pts) bounds.extend(f.geometry.coordinates as [number, number]);
        map.fitBounds(bounds, { padding: 56, maxZoom: 14, duration: 0 });
      }
      syncMarkers();
      reportView();
    });

    // Recompute the marker set only when the view settles or clustering
    // recomputes — maplibre repositions existing DOM markers each frame on its
    // own, so a per-frame handler would thrash the main thread on large sets.
    map.on("moveend", () => { syncMarkers(); reportView(); });
    map.on("sourcedata", (e) => { if (e.sourceId === "exhibitions" && e.isSourceLoaded) syncMarkers(); });

    // Zoom into a cluster on click.
    map.on("click", "clusters", async (ev) => {
      const feature = ev.features?.[0];
      if (!feature) return;
      const clusterId = feature.properties?.cluster_id as number;
      const src = map.getSource("exhibitions") as GeoJSONSource;
      const zoom = await src.getClusterExpansionZoom(clusterId);
      map.easeTo({ center: (feature.geometry as GeoJSON.Point).coordinates as [number, number], zoom });
    });

    const setPointer = (on: boolean) => () => {
      map.getCanvas().style.cursor = on ? "pointer" : "";
    };
    map.on("mouseenter", "clusters", setPointer(true));
    map.on("mouseleave", "clusters", setPointer(false));

    return () => {
      for (const id in markers) markers[id].remove();
      markerEls.current = {};
      map.remove();
      mapRef.current = null;
    };
  }, [items]);

  // 시트로 선택된 venue 마커를 강조 (지도 재생성 없이 클래스만 토글).
  useEffect(() => {
    for (const id in markerEls.current) {
      markerEls.current[id].classList.toggle("frame-poster-marker--selected", id === selectedVenueId);
    }
  }, [selectedVenueId, items]);

  // "내 위치" marker + fly there, without rebuilding the map.
  const hereMarker = useRef<maplibregl.Marker | null>(null);
  useEffect(() => {
    const map = mapRef.current;
    if (!map || !userLocation) return;
    if (!hereMarker.current) {
      const el = document.createElement("div");
      el.className = "frame-here-marker";
      hereMarker.current = new maplibregl.Marker({ element: el });
    }
    hereMarker.current.setLngLat(userLocation).addTo(map);
    map.flyTo({ center: userLocation, zoom: Math.max(map.getZoom(), 12), duration: 700 });
  }, [userLocation]);

  return (
    <div
      ref={ref}
      style={{ height }}
      className="w-full overflow-hidden rounded-2xl border border-line [&_.maplibregl-ctrl-attrib]:bg-black/60 [&_.maplibregl-ctrl-attrib_a]:text-tx2"
    />
  );
}
