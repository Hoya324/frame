import { CINEMA_MODERN, CINEMA_PD, type CinemaScene } from "@/lib/cinema";
import type { Locale } from "@/lib/i18n";

// Search / sort / filter for the cinema collection — mirrors the exhibition
// helpers in lib/filters.ts + lib/sort.ts, but typed to CinemaScene.

export type CinemaKind = "modern" | "pd";
export type CinemaSortKey = "newest" | "oldest" | "name";

export interface CinemaEntry {
  scene: CinemaScene;
  kind: CinemaKind;
  year: number;
}

// The release year is embedded in the credit line ("… · 2019"); parse it once
// rather than duplicating it as a separate data field.
export function yearOf(scene: CinemaScene): number {
  const m = (scene.credit.en || scene.credit.ko).match(/\b(18|19|20)\d{2}\b/);
  return m ? parseInt(m[0], 10) : 0;
}

export function decadeOf(year: number): number {
  return year > 0 ? Math.floor(year / 10) * 10 : 0;
}

export function cinemaEntries(): CinemaEntry[] {
  return [
    ...CINEMA_MODERN.map((s): CinemaEntry => ({ scene: s, kind: "modern", year: yearOf(s) })),
    ...CINEMA_PD.map((s): CinemaEntry => ({ scene: s, kind: "pd", year: yearOf(s) })),
  ];
}

export function presentDecades(items: CinemaEntry[]): number[] {
  return [...new Set(items.map((e) => decadeOf(e.year)).filter((d) => d > 0))].sort((a, b) => b - a);
}

export function searchCinema(items: CinemaEntry[], q: string): CinemaEntry[] {
  const query = q.trim().toLowerCase();
  if (!query) return items;
  return items.filter(({ scene }) => {
    const hay = [
      scene.title.ko, scene.title.en, scene.title.ja,
      scene.credit.ko, scene.credit.en, scene.studio ?? "",
    ].join(" ").toLowerCase();
    return hay.includes(query);
  });
}

export interface CinemaFilter {
  kinds: CinemaKind[];
  decades: number[];
}

export function filterCinema(items: CinemaEntry[], f: CinemaFilter): CinemaEntry[] {
  return items.filter((e) => {
    if (f.kinds.length && !f.kinds.includes(e.kind)) return false;
    if (f.decades.length && !f.decades.includes(decadeOf(e.year))) return false;
    return true;
  });
}

// Non-destructive sort. Ties break by English title so order is deterministic.
export function sortCinema(items: CinemaEntry[], key: CinemaSortKey, locale: Locale): CinemaEntry[] {
  const copy = [...items];
  if (key === "newest") {
    copy.sort((a, b) => b.year - a.year || a.scene.title.en.localeCompare(b.scene.title.en));
  } else if (key === "oldest") {
    copy.sort((a, b) => a.year - b.year || a.scene.title.en.localeCompare(b.scene.title.en));
  } else {
    copy.sort((a, b) => a.scene.title[locale].localeCompare(b.scene.title[locale], locale));
  }
  return copy;
}
