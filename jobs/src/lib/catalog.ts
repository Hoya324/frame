import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { dirname, resolve } from "node:path";

export interface JobExhibition {
  id: string; title: string;
  medium: string | null; exhibitionType: string | null;
  genreTags: string[]; feeType: string | null;
  startDate: string | null; endDate: string | null; status: string;
  posterImageUrl: string | null; sourceUrl: string | null;
  venueName: string | null; region: string | null; artistNames: string[];
}
export interface JobCatalog { generatedAt: string; exhibitions: JobExhibition[]; }

/* eslint-disable @typescript-eslint/no-explicit-any */
export function parseCatalog(raw: any): JobCatalog {
  return {
    generatedAt: raw.generated_at,
    exhibitions: (raw.exhibitions ?? []).map((e: any): JobExhibition => ({
      id: e.id, title: e.title,
      medium: e.medium ?? null, exhibitionType: e.exhibition_type ?? null,
      genreTags: e.genre_tags ?? [], feeType: e.fee_type ?? null,
      startDate: e.start_date ?? null, endDate: e.end_date ?? null, status: e.status ?? "unknown",
      posterImageUrl: e.poster_image_url ?? null, sourceUrl: e.source_url ?? null,
      venueName: e.venue?.name ?? null, region: e.venue?.region ?? null,
      artistNames: (e.artists ?? []).map((a: any) => a.name),
    })),
  };
}

export function loadCatalog(): JobCatalog {
  const here = dirname(fileURLToPath(import.meta.url));
  const path = resolve(here, "../../../web/public/data/exhibitions.json");
  return parseCatalog(JSON.parse(readFileSync(path, "utf8")));
}

const MS_PER_DAY = 86_400_000;
function atMidnight(d: Date): number {
  return Math.floor(new Date(d.getFullYear(), d.getMonth(), d.getDate()).getTime() / MS_PER_DAY);
}
export function daysUntil(endDate: string | null, today: Date = new Date()): number | null {
  if (!endDate) return null;
  return atMidnight(new Date(endDate + "T00:00:00")) - atMidnight(today);
}
