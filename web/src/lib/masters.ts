import type { TrMap } from "@/lib/catalog";

export type Region = "kr" | "jp" | "modern" | "foreign";

export interface MasterWork {
  id: string;
  title: string;
  year: string | null;
  medium: string | null;
  imageUrl: string | null;
  thumbUrl: string | null;
  source: string | null;
  sourceUrl: string | null;
  credit: string | null;
  commentary: string | null;
  lang: string | null;
  tr: TrMap;
}

export interface Master {
  id: string;
  name: string;
  region: Region;
  nationality: string | null;
  birthYear: number | null;
  deathYear: number | null;
  tagline: string | null;
  bio: string | null;
  portraitUrl: string | null;
  lang: string | null;
  tr: TrMap;
  works: MasterWork[];
}

export interface MastersCatalog {
  generatedAt: string;
  masters: Master[];
}

/* eslint-disable @typescript-eslint/no-explicit-any */

function trOf(v: any): TrMap {
  return v && typeof v === "object" ? (v as TrMap) : {};
}

function parseWork(w: any): MasterWork {
  return {
    id: w.id, title: w.title ?? "", year: w.year ?? null, medium: w.medium ?? null,
    imageUrl: w.imageUrl ?? null, thumbUrl: w.thumbUrl ?? w.imageUrl ?? null,
    source: w.source ?? null, sourceUrl: w.sourceUrl ?? null, credit: w.credit ?? null,
    commentary: w.commentary ?? null, lang: w.lang ?? "ko", tr: trOf(w.tr),
  };
}

export function parseMasters(raw: any): MastersCatalog {
  return {
    generatedAt: raw.generated_at ?? raw.generatedAt ?? "",
    masters: (raw.masters ?? []).map((m: any): Master => ({
      id: m.id, name: m.name ?? "", region: (m.region ?? "foreign") as Region,
      nationality: m.nationality ?? null, birthYear: m.birthYear ?? null,
      deathYear: m.deathYear ?? null, tagline: m.tagline ?? null, bio: m.bio ?? null,
      portraitUrl: m.portraitUrl ?? null, lang: m.lang ?? "ko", tr: trOf(m.tr),
      works: (m.works ?? []).map(parseWork),
    })),
  };
}

export async function loadMasters(): Promise<MastersCatalog> {
  const data = (await import("../../public/data/masters.json")).default;
  return parseMasters(data);
}

// Convenience: the image to show for a master in lists/carousels — portrait if
// present, else the first work's image.
export function masterFaceImage(m: Master): string | null {
  return m.portraitUrl ?? m.works.find((w) => w.thumbUrl || w.imageUrl)?.thumbUrl ?? null;
}

export function masterHeroImage(m: Master): string | null {
  return m.works.find((w) => w.imageUrl)?.imageUrl ?? m.portraitUrl ?? null;
}
