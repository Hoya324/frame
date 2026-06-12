import { describe, expect, it } from "vitest";
import {
  cinemaEntries, decadeOf, filterCinema, presentDecades, searchCinema,
  sortCinema, yearOf, type CinemaEntry,
} from "./cinemaFilter";
import type { CinemaScene } from "./cinema";

function scene(id: string, ko: string, en: string, year: number, studio?: string): CinemaScene {
  return {
    id, title: { ko, en, ja: ko }, credit: { ko: `감독 · ${year}`, en: `Dir · ${year}`, ja: `監督 · ${year}` },
    lesson: { ko: "l", en: "l", ja: "l" }, url: "https://x", image: "https://img", studio,
  };
}
function entry(s: CinemaScene, kind: "modern" | "pd" = "modern"): CinemaEntry {
  return { scene: s, kind, year: yearOf(s) };
}

describe("cinemaFilter", () => {
  it("parses the year out of the credit line", () => {
    expect(yearOf(scene("a", "가", "A", 1994))).toBe(1994);
    expect(decadeOf(1994)).toBe(1990);
    expect(decadeOf(2017)).toBe(2010);
  });

  it("cinemaEntries tags modern vs pd and is non-empty", () => {
    const all = cinemaEntries();
    expect(all.length).toBeGreaterThan(100);
    expect(all.some((e) => e.kind === "modern")).toBe(true);
    expect(all.some((e) => e.kind === "pd")).toBe(true);
  });

  it("searches title (any locale), director and studio", () => {
    const items = [entry(scene("a", "기생충", "Parasite", 2019, "Barunson")),
                   entry(scene("b", "올드보이", "Oldboy", 2003))];
    expect(searchCinema(items, "parasite").map((e) => e.scene.id)).toEqual(["a"]);
    expect(searchCinema(items, "기생충").map((e) => e.scene.id)).toEqual(["a"]);
    expect(searchCinema(items, "barunson").map((e) => e.scene.id)).toEqual(["a"]);
    expect(searchCinema(items, "").length).toBe(2); // empty query → all
  });

  it("sorts newest, oldest and by name", () => {
    const items = [entry(scene("old", "나", "Older", 1975)),
                   entry(scene("new", "가", "Newer", 2020))];
    expect(sortCinema(items, "newest", "en").map((e) => e.scene.id)).toEqual(["new", "old"]);
    expect(sortCinema(items, "oldest", "en").map((e) => e.scene.id)).toEqual(["old", "new"]);
    // name sort uses the locale title; ko "가" < "나"
    expect(sortCinema(items, "name", "ko").map((e) => e.scene.id)).toEqual(["new", "old"]);
  });

  it("filters by kind and by decade", () => {
    const items = [entry(scene("m", "가", "A", 2019), "modern"),
                   entry(scene("p", "나", "B", 1925), "pd")];
    expect(filterCinema(items, { kinds: ["pd"], decades: [] }).map((e) => e.scene.id)).toEqual(["p"]);
    expect(filterCinema(items, { kinds: [], decades: [2010] }).map((e) => e.scene.id)).toEqual(["m"]);
    expect(filterCinema(items, { kinds: [], decades: [] }).length).toBe(2); // no filter → all
  });

  it("presentDecades lists only decades that occur, newest first", () => {
    const items = [entry(scene("a", "가", "A", 2019)), entry(scene("b", "나", "B", 1925)),
                   entry(scene("c", "다", "C", 2017))];
    expect(presentDecades(items)).toEqual([2010, 1920]);
  });
});
