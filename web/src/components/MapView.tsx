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

function toFeatureCollection(items: Exhibition[]): GeoJSON.FeatureCollection<GeoJSON.Point> {
  const features: GeoJSON.Feature<GeoJSON.Point>[] = [];
  for (const e of items) {
    const { lat, lng } = e.venue ?? {};
    if (lat == null || lng == null) continue;
    features.push({
      type: "Feature",
      geometry: { type: "Point", coordinates: [lng, lat] },
      properties: { id: e.id, title: e.title, venue: e.venue?.name ?? "" },
    });
  }
  return { type: "FeatureCollection", features };
}

export function MapView({ items, height = 480, onSelect }:
  { items: Exhibition[]; height?: number; onSelect?: (id: string) => void }) {
  const ref = useRef<HTMLDivElement>(null);
  // Keep latest onSelect without re-initializing the map on every render.
  const onSelectRef = useRef(onSelect);
  useEffect(() => {
    onSelectRef.current = onSelect;
  }, [onSelect]);

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
    map.addControl(new maplibregl.NavigationControl({ showCompass: false }), "top-right");

    const hoverPopup = new maplibregl.Popup({
      offset: 14,
      closeButton: false,
      closeOnClick: false,
      className: "frame-map-popup",
    });

    map.on("load", () => {
      map.addSource("exhibitions", {
        type: "geojson",
        data,
        cluster: true,
        clusterRadius: 48,
        clusterMaxZoom: 14,
      });

      map.addLayer({
        id: "clusters",
        type: "circle",
        source: "exhibitions",
        filter: ["has", "point_count"],
        paint: {
          "circle-color": "#ffffff",
          "circle-opacity": 0.92,
          // Grow the disc with the number of points it represents.
          "circle-radius": ["step", ["get", "point_count"], 16, 10, 21, 30, 27],
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
          "text-field": ["get", "point_count_abbreviated"],
          "text-font": ["Open Sans Bold", "Arial Unicode MS Bold"],
          "text-size": 13,
        },
        paint: { "text-color": "#000000" },
      });
      map.addLayer({
        id: "unclustered-point",
        type: "circle",
        source: "exhibitions",
        filter: ["!", ["has", "point_count"]],
        paint: {
          "circle-color": "#ffffff",
          "circle-radius": 6,
          "circle-stroke-width": 2,
          "circle-stroke-color": "#000000",
        },
      });

      if (pts.length > 1) {
        const bounds = new maplibregl.LngLatBounds();
        for (const f of pts) bounds.extend(f.geometry.coordinates as [number, number]);
        map.fitBounds(bounds, { padding: 56, maxZoom: 14, duration: 0 });
      }
    });

    // Zoom into a cluster on click.
    map.on("click", "clusters", async (ev) => {
      const feature = ev.features?.[0];
      if (!feature) return;
      const clusterId = feature.properties?.cluster_id as number;
      const src = map.getSource("exhibitions") as GeoJSONSource;
      const zoom = await src.getClusterExpansionZoom(clusterId);
      map.easeTo({ center: (feature.geometry as GeoJSON.Point).coordinates as [number, number], zoom });
    });

    map.on("click", "unclustered-point", (ev) => {
      const id = ev.features?.[0]?.properties?.id as string | undefined;
      if (id) onSelectRef.current?.(id);
    });

    const setPointer = (on: boolean) => () => {
      map.getCanvas().style.cursor = on ? "pointer" : "";
    };
    map.on("mouseenter", "clusters", setPointer(true));
    map.on("mouseleave", "clusters", setPointer(false));
    map.on("mouseenter", "unclustered-point", (ev) => {
      map.getCanvas().style.cursor = "pointer";
      const f = ev.features?.[0];
      if (!f) return;
      const p = f.properties ?? {};
      hoverPopup
        .setLngLat((f.geometry as GeoJSON.Point).coordinates as [number, number])
        .setHTML(
          `<div style="max-width:200px">
             <div style="font-weight:700;font-size:13px;line-height:1.3">${escapeHtml(String(p.title ?? ""))}</div>
             <div style="color:#9a9a9a;font-size:11px;margin-top:2px">${escapeHtml(String(p.venue ?? ""))}</div>
           </div>`,
        )
        .addTo(map);
    });
    map.on("mouseleave", "unclustered-point", () => {
      map.getCanvas().style.cursor = "";
      hoverPopup.remove();
    });

    return () => map.remove();
  }, [items]);

  return (
    <div
      ref={ref}
      style={{ height }}
      className="w-full overflow-hidden rounded-2xl border border-line [&_.maplibregl-ctrl-attrib]:bg-black/60 [&_.maplibregl-ctrl-attrib_a]:text-tx2"
    />
  );
}

function escapeHtml(s: string): string {
  return s.replace(/[&<>"']/g, (c) =>
    ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[c]!,
  );
}
