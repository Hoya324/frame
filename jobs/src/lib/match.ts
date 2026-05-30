import { daysUntil, type JobExhibition } from "./catalog";

export interface CustomFilters {
  artists?: string[];
  regions?: string[];
  genres?: string[];
  mediums?: string[];
}

export function closingSoonForReminder(
  list: JobExhibition[],
  today: Date = new Date(),
  offsets: number[] = [3, 1],
): JobExhibition[] {
  const set = new Set(offsets);
  return list.filter((e) => {
    if (e.status !== "ongoing") return false;
    const d = daysUntil(e.endDate, today);
    return d != null && set.has(d);
  });
}

export function matchCustom(list: JobExhibition[], f: CustomFilters): JobExhibition[] {
  const dims: { values: string[] | undefined; pick: (e: JobExhibition) => string[] }[] = [
    { values: f.regions, pick: (e) => (e.region ? [e.region] : []) },
    { values: f.mediums, pick: (e) => (e.medium ? [e.medium] : []) },
    { values: f.artists, pick: (e) => e.artistNames },
    { values: f.genres, pick: (e) => e.genreTags },
  ];
  const active = dims.filter((d) => d.values && d.values.length > 0);
  if (active.length === 0) return [];
  return list.filter((e) =>
    active.every((d) => d.pick(e).some((v) => d.values!.includes(v))),
  );
}
