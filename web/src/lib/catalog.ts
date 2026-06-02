export type Status = "upcoming" | "ongoing" | "past" | "unknown";

import type { Locale } from "@/lib/i18n";

// Translation map: locale -> field -> translated text. The original-language key is NOT present.
export type TrMap = Partial<Record<Locale, Record<string, string>>>;

export interface VenueEmbed {
  id: string; name: string; region: string | null; district: string | null;
  lat: number | null; lng: number | null;
  lang: string | null; tr: TrMap;
}
export interface Exhibition {
  id: string; source: string | null; title: string;
  posterImageUrl: string | null; description: string | null;
  medium: string | null; exhibitionType: string | null; genreTags: string[];
  feeType: string | null; priceMin: number | null; priceMax: number | null;
  startDate: string | null; endDate: string | null;
  status: Status; openHours: string | null;
  venue: VenueEmbed | null;
  artists: { id: string; name: string; lang: string | null; tr: TrMap }[];
  sourceUrl: string | null; featured: boolean; popularityScore: number | null;
  lang: string | null; tr: TrMap;
}
export interface Venue {
  id: string; name: string; venueType: string | null;
  region: string | null; district: string | null; address: string | null;
  country: string | null; lat: number | null; lng: number | null; website: string | null;
  lang: string | null; tr: TrMap;
}
export interface Catalog {
  generatedAt: string;
  exhibitions: Exhibition[];
  venues: Venue[];
  artists: { id: string; name: string; lang: string | null; tr: TrMap }[];
}

/* eslint-disable @typescript-eslint/no-explicit-any */

// Collapse records sharing an id, last occurrence winning — mirrors the
// crawler's upsert dedup so the UI stays correct even on a pre-dedup data file.
function dedupeById<T extends { id: string }>(items: T[]): T[] {
  const byId = new Map<string, T>();
  for (const item of items) byId.set(item.id, item);
  return [...byId.values()];
}

function trOf(v: any): TrMap {
  return v && typeof v === "object" ? (v as TrMap) : {};
}

export function parseCatalog(raw: any): Catalog {
  return {
    generatedAt: raw.generated_at,
    exhibitions: dedupeById((raw.exhibitions ?? []).map(
      (e: any): Exhibition => ({
        id: e.id, source: e.source ?? null, title: e.title,
        posterImageUrl: e.poster_image_url ?? null, description: e.description ?? null,
        medium: e.medium ?? null, exhibitionType: e.exhibition_type ?? null,
        genreTags: e.genre_tags ?? [], feeType: e.fee_type ?? null,
        priceMin: e.price_min ?? null, priceMax: e.price_max ?? null,
        startDate: e.start_date ?? null, endDate: e.end_date ?? null,
        status: (e.status ?? "unknown") as Status, openHours: e.open_hours ?? null,
        venue: e.venue
          ? { id: e.venue.id, name: e.venue.name, region: e.venue.region ?? null,
              district: e.venue.district ?? null, lat: e.venue.lat ?? null, lng: e.venue.lng ?? null,
              lang: e.venue.lang ?? null, tr: trOf(e.venue.tr) }
          : null,
        artists: (e.artists ?? []).map((a: any) => ({ id: a.id, name: a.name, lang: a.lang ?? null, tr: trOf(a.tr) })),
        sourceUrl: e.source_url ?? null, featured: !!e.featured,
        popularityScore: e.popularity_score ?? null,
        lang: e.lang ?? null, tr: trOf(e.tr),
      }),
    )),
    venues: dedupeById((raw.venues ?? []).map((v: any): Venue => ({
      id: v.id, name: v.name, venueType: v.venue_type ?? null,
      region: v.region ?? null, district: v.district ?? null, address: v.address ?? null,
      country: v.country ?? null, lat: v.lat ?? null, lng: v.lng ?? null, website: v.website ?? null,
      lang: v.lang ?? null, tr: trOf(v.tr),
    }))),
    artists: dedupeById((raw.artists ?? []).map((a: any) => ({ id: a.id, name: a.name, lang: a.lang ?? null, tr: trOf(a.tr) }))),
  };
}

export async function loadCatalog(): Promise<Catalog> {
  const data = (await import("../../public/data/exhibitions.json")).default;
  return parseCatalog(data);
}

// Returns the translation for the current locale if present, else null (= caller uses the original text).
export function localized(
  original: string | null | undefined,
  tr: TrMap | undefined,
  locale: Locale,
  field: string,
): string | null {
  const text = tr?.[locale]?.[field];
  if (!text) return null;
  if (text === (original ?? "")) return null;
  return text;
}
