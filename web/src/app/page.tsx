"use client";
import { useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { loadCatalogSync } from "@/lib/catalogClient";
import { applyFilters, type FilterState } from "@/lib/filters";
import { isClosingSoon } from "@/lib/status";
import { sortExhibitions, type SortKey } from "@/lib/sort";
import { ExhibitionCard } from "@/components/ExhibitionCard";
import { FilterChips } from "@/components/FilterChips";
import { FilterGroup } from "@/components/controls/FilterGroup";
import { SortChips } from "@/components/controls/SortChips";
import { PosterImage } from "@/components/PosterImage";
import { SwipeDeck } from "@/components/SwipeDeck";
import { useLang } from "@/components/LanguageProvider";
import { EVENTS, track } from "@/lib/analytics";
import type { Exhibition } from "@/lib/catalog";

export default function Home() {
  const catalog = loadCatalogSync();
  const today = new Date();
  const { t } = useLang();
  const STATUS_OPTS = [
    { value: "ongoing", label: t("filter.ongoing") },
    { value: "upcoming", label: t("filter.upcoming") },
    { value: "past", label: t("filter.past") },
  ];
  const EXTRA_OPTS = [
    { value: "free", label: t("filter.free") },
    { value: "photo", label: t("filter.photo") },
    { value: "solo", label: t("filter.solo") },
  ];
  const [mode, setMode] = useState<"time" | "swipe">("time");
  const [chips, setChips] = useState<string[]>([]);
  const [sort, setSort] = useState<SortKey>("recommended");
  const toggle = (v: string) => setChips((c) => (c.includes(v) ? c.filter((x) => x !== v) : [...c, v]));
  const selectMode = (m: "time" | "swipe") => {
    if (m !== mode) track(EVENTS.homeViewMode, { mode: m });
    setMode(m);
  };

  // Swipe mode is a fixed, full-viewport view — lock page scroll while it's active.
  useEffect(() => {
    if (mode !== "swipe") return;
    const prev = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    return () => { document.body.style.overflow = prev; };
  }, [mode]);
  const swipeMode = mode === "swipe";

  const f: FilterState = useMemo(() => ({
    statuses: chips.filter((c) => ["ongoing", "upcoming", "past"].includes(c)) as FilterState["statuses"],
    mediums: chips.includes("photo") ? ["photo"] : [],
    types: chips.includes("solo") ? ["solo"] : [],
    freeOnly: chips.includes("free"),
    regions: [],
  }), [chips]);

  const list = applyFilters(catalog.exhibitions, f);

  const featured = catalog.exhibitions.find((e) => e.featured) ?? catalog.exhibitions[0];
  const closingSoon = catalog.exhibitions
    .filter((e) => e.status === "ongoing" && isClosingSoon(e.endDate, today))
    .sort((a, b) => (a.endDate ?? "").localeCompare(b.endDate ?? ""));
  const mainList = sortExhibitions(list, sort, { today });

  const counts = {
    ongoing: catalog.exhibitions.filter((e) => e.status === "ongoing").length,
    closing: closingSoon.length,
    upcoming: catalog.exhibitions.filter((e) => e.status === "upcoming").length,
  };

  return (
    <main
      className={
        swipeMode
          ? "mx-auto flex h-[calc(100dvh-9rem)] max-w-[1180px] flex-col overflow-hidden px-7 md:h-[calc(100dvh-3.5rem)]"
          : "mx-auto max-w-[1180px] px-7"
      }
    >
      <div className={swipeMode ? "shrink-0 pt-6" : "py-10"}>
        {!swipeMode && (
          <>
            <h1 className="text-[38px] font-extrabold leading-none tracking-tight">{t("home.heading")}</h1>
            <p className="mt-3 text-sm text-tx2">
              {t("home.ongoing")} <b className="text-tx">{counts.ongoing}</b> · {t("home.closing")}{" "}
              <b className="text-tx">{counts.closing}</b> · {t("home.upcoming")} <b className="text-tx">{counts.upcoming}</b>
            </p>
          </>
        )}
        <div className={`flex gap-2 ${swipeMode ? "" : "mt-4"}`}>
          <button
            type="button"
            onClick={() => selectMode("time")}
            className={`rounded-full px-4 py-1.5 text-sm transition ${
              mode === "time"
                ? "bg-white font-semibold text-black"
                : "border border-line text-tx2 hover:text-tx"
            }`}
          >
            {t("home.tabTime")}
          </button>
          <button
            type="button"
            onClick={() => selectMode("swipe")}
            className={`rounded-full px-4 py-1.5 text-sm transition ${
              mode === "swipe"
                ? "bg-white font-semibold text-black"
                : "border border-line text-tx2 hover:text-tx"
            }`}
          >
            {t("home.tabSwipe")}
          </button>
        </div>
      </div>

      {!swipeMode && (
        <>
          <div className="flex flex-wrap items-center gap-x-3 gap-y-2 pb-7">
            <FilterGroup label={t("controls.status")}>
              <FilterChips options={STATUS_OPTS} active={chips} onToggle={toggle} />
            </FilterGroup>
            <span className="h-4 w-px bg-line2" aria-hidden="true" />
            <FilterGroup label={t("controls.more")}>
              <FilterChips options={EXTRA_OPTS} active={chips} onToggle={toggle} />
            </FilterGroup>
            <span className="h-4 w-px bg-line2" aria-hidden="true" />
            <FilterGroup label={t("controls.sort")}>
              <SortChips value={sort} options={["recommended", "closing", "recent"]} onChange={setSort} context="home" />
            </FilterGroup>
          </div>

          {featured && (
            <section className="mb-9 grid overflow-hidden rounded border border-line md:grid-cols-[1.1fr_0.9fr]">
              <div className="relative min-h-[320px]">
                <ExhibitionCardHero e={featured} />
              </div>
            </section>
          )}

          {closingSoon.length > 0 && (
            <Section title={t("home.sectionClosing")} hint={t("home.sectionClosingHint")}>
              {closingSoon.slice(0, 4).map((e) => <ExhibitionCard key={e.id} exhibition={e} today={today} />)}
            </Section>
          )}
          <Section title={t("home.sectionOngoing")} hint={t("home.sectionOngoingHint")}>
            {mainList.map((e) => <ExhibitionCard key={e.id} exhibition={e} today={today} />)}
          </Section>
        </>
      )}

      {swipeMode && (
        <>
          <div className="shrink-0 py-4">
            <div className="flex flex-wrap items-center gap-x-3 gap-y-2">
              <FilterGroup label={t("controls.status")}>
                <FilterChips options={STATUS_OPTS} active={chips} onToggle={toggle} />
              </FilterGroup>
              <span className="h-4 w-px bg-line2" aria-hidden="true" />
              <FilterGroup label={t("controls.more")}>
                <FilterChips options={EXTRA_OPTS} active={chips} onToggle={toggle} />
              </FilterGroup>
            </div>
          </div>
          <div className="min-h-0 flex-1 pb-4">
            {/* Same filtered + sorted list as the time view, but a swipe deck is
                for finding something to go see — so drop ended shows unless the
                user explicitly opts into 종료. Re-key on filter + sort so the
                deck rebuilds from the new list (not on a bookmark toggle). */}
            <SwipeDeck
              key={`${chips.join(",")}-${sort}`}
              items={chips.includes("past") ? mainList : mainList.filter((e) => e.status !== "past")}
            />
          </div>
        </>
      )}
    </main>
  );
}

function Section({ title, hint, children }: { title: string; hint: string; children: React.ReactNode }) {
  return (
    <section className="pb-11">
      <div className="mb-4 flex items-baseline gap-3">
        <h3 className="text-lg font-bold tracking-tight">{title}</h3>
        <span className="text-[13px] text-tx3">{hint}</span>
      </div>
      <div className="grid grid-cols-2 gap-4 md:grid-cols-4">{children}</div>
    </section>
  );
}

function ExhibitionCardHero({ e }: { e: Exhibition }) {
  const { t } = useLang();
  return (
    <Link href={`/exhibitions/${e.id}`} className="absolute inset-0">
      <PosterImage src={e.posterImageUrl} alt={e.title} />
      <div className="absolute inset-x-0 bottom-0 bg-gradient-to-t from-black/90 to-transparent p-6">
        <div className="text-[11px] font-semibold uppercase tracking-widest text-tx2">{t("home.featured")}</div>
        <h2 className="mt-2 text-2xl font-extrabold tracking-tight">{e.title}</h2>
        <div className="mt-2 text-sm text-tx2">
          {e.venue?.name} · {e.startDate}–{e.endDate}
        </div>
      </div>
    </Link>
  );
}
