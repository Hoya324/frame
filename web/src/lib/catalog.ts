export type Status = "upcoming" | "ongoing" | "past" | "unknown";

export interface VenueEmbed {
  id: string; name: string; region: string | null; district: string | null;
  lat: number | null; lng: number | null;
}
export interface Exhibition {
  id: string; title: string; titleEn: string | null;
  posterImageUrl: string | null; description: string | null;
  medium: string | null; exhibitionType: string | null; genreTags: string[];
  feeType: string | null; priceMin: number | null; priceMax: number | null;
  startDate: string | null; endDate: string | null;
  status: Status; openHours: string | null;
  venue: VenueEmbed | null; artists: { id: string; name: string }[];
  sourceUrl: string | null; featured: boolean; popularityScore: number | null;
}
export interface Venue {
  id: string; name: string; nameEn: string | null; venueType: string | null;
  region: string | null; district: string | null; address: string | null;
  country: string | null; lat: number | null; lng: number | null; website: string | null;
}
export interface Catalog {
  generatedAt: string;
  exhibitions: Exhibition[];
  venues: Venue[];
  artists: { id: string; name: string; nameEn: string | null }[];
}

/* eslint-disable @typescript-eslint/no-explicit-any */
export function parseCatalog(raw: any): Catalog {
  return {
    generatedAt: raw.generated_at,
    exhibitions: (raw.exhibitions ?? []).map(
      (e: any): Exhibition => ({
        id: e.id, title: e.title, titleEn: e.title_en ?? null,
        posterImageUrl: e.poster_image_url ?? null, description: e.description ?? null,
        medium: e.medium ?? null, exhibitionType: e.exhibition_type ?? null,
        genreTags: e.genre_tags ?? [], feeType: e.fee_type ?? null,
        priceMin: e.price_min ?? null, priceMax: e.price_max ?? null,
        startDate: e.start_date ?? null, endDate: e.end_date ?? null,
        status: (e.status ?? "unknown") as Status, openHours: e.open_hours ?? null,
        venue: e.venue
          ? { id: e.venue.id, name: e.venue.name, region: e.venue.region ?? null,
              district: e.venue.district ?? null, lat: e.venue.lat ?? null, lng: e.venue.lng ?? null }
          : null,
        artists: e.artists ?? [],
        sourceUrl: e.source_url ?? null, featured: !!e.featured,
        popularityScore: e.popularity_score ?? null,
      }),
    ),
    venues: (raw.venues ?? []).map((v: any): Venue => ({
      id: v.id, name: v.name, nameEn: v.name_en ?? null, venueType: v.venue_type ?? null,
      region: v.region ?? null, district: v.district ?? null, address: v.address ?? null,
      country: v.country ?? null, lat: v.lat ?? null, lng: v.lng ?? null, website: v.website ?? null,
    })),
    artists: (raw.artists ?? []).map((a: any) => ({ id: a.id, name: a.name, nameEn: a.name_en ?? null })),
  };
}

export async function loadCatalog(): Promise<Catalog> {
  const data = (await import("../../public/data/exhibitions.json")).default;
  return parseCatalog(data);
}
