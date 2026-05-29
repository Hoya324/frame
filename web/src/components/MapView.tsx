"use client";
import { useEffect, useRef } from "react";
import maplibregl from "maplibre-gl";
import "maplibre-gl/dist/maplibre-gl.css";
import type { Exhibition } from "@/lib/catalog";

const STYLE = "https://demotiles.maplibre.org/style.json"; // free OSM-based; swap for a richer style later

export function MapView({ items, height = 480, onSelect }:
  { items: Exhibition[]; height?: number; onSelect?: (id: string) => void }) {
  const ref = useRef<HTMLDivElement>(null);
  useEffect(() => {
    if (!ref.current) return;
    const pts = items.filter((e) => e.venue?.lat != null && e.venue?.lng != null);
    const map = new maplibregl.Map({
      container: ref.current, style: STYLE,
      center: pts[0] ? [pts[0].venue!.lng!, pts[0].venue!.lat!] : [126.98, 37.57], zoom: 11,
    });
    for (const e of pts) {
      const el = document.createElement("button");
      el.className = "h-3 w-3 rounded-full border-2 border-white bg-black";
      el.setAttribute("aria-label", e.title);
      el.onclick = () => onSelect?.(e.id);
      new maplibregl.Marker({ element: el }).setLngLat([e.venue!.lng!, e.venue!.lat!]).addTo(map);
    }
    return () => map.remove();
  }, [items, onSelect]);
  return <div ref={ref} style={{ height }} className="w-full overflow-hidden rounded border border-line" />;
}
