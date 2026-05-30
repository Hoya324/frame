"use client";
import { useMemo, useState } from "react";
import Link from "next/link";
import { loadCatalogSync } from "@/lib/catalogClient";
import { applyFilters, type FilterState } from "@/lib/filters";
import { isClosingSoon } from "@/lib/status";
import { ExhibitionCard } from "@/components/ExhibitionCard";
import { FilterChips } from "@/components/FilterChips";
import { PosterImage } from "@/components/PosterImage";
import { SwipeDeck } from "@/components/SwipeDeck";
import { useLang } from "@/components/LanguageProvider";
import { bilingual } from "@/lib/i18n";
import type { Exhibition } from "@/lib/catalog";

export default function Home() {
  const catalog = loadCatalogSync();
  const today = new Date();
  const { t } = useLang();
  const STATUS_OPTS = [
    { value: "ongoing", label: t("filter.ongoing") },
    { value: "closing", label: t("filter.closing") },
    { value: "upcoming", label: t("filter.upcoming") },
  ];
  const EXTRA_OPTS = [
    { value: "free", label: t("filter.free") },
    { value: "photo", label: t("filter.photo") },
    { value: "solo", label: t("filter.solo") },
  ];
  const [mode, setMode] = useState<"time" | "swipe">("time");
  const [chips, setChips] = useState<string[]>([]);
  const toggle = (v: string) => setChips((c) => (c.includes(v) ? c.filter((x) => x !== v) : [...c, v]));

  const f: FilterState = useMemo(() => ({
    statuses: chips.filter((c) => ["ongoing", "upcoming"].includes(c)) as FilterState["statuses"],
    mediums: chips.includes("photo") ? ["photo"] : [],
    types: chips.includes("solo") ? ["solo"] : [],
    freeOnly: chips.includes("free"),
    regions: [],
  }), [chips]);

  let list = applyFilters(catalog.exhibitions, f);
  if (chips.includes("closing")) list = list.filter((e) => isClosingSoon(e.endDate, today));

  const featured = catalog.exhibitions.find((e) => e.featured) ?? catalog.exhibitions[0];
  const closingSoon = catalog.exhibitions
    .filter((e) => e.status === "ongoing" && isClosingSoon(e.endDate, today))
    .sort((a, b) => (a.endDate ?? "").localeCompare(b.endDate ?? ""));
  const ongoing = list.filter((e) => e.status === "ongoing");

  const counts = {
    ongoing: catalog.exhibitions.filter((e) => e.status === "ongoing").length,
    closing: closingSoon.length,
    upcoming: catalog.exhibitions.filter((e) => e.status === "upcoming").length,
  };

  return (
    <main className="mx-auto max-w-[1180px] px-7">
      <div className="py-10">
        <div className="text-xs font-semibold uppercase tracking-wide text-tx3">
          {today.toISOString().slice(0, 10)} · {t("home.todayTag").split("·").pop()?.trim()}
        </div>
        <h1 className="mt-2.5 text-[38px] font-extrabold leading-none tracking-tight">{t("home.heading")}</h1>
        <p className="mt-3 text-sm text-tx2">
          {t("home.ongoing")} <b className="text-tx">{counts.ongoing}</b> · {t("home.closing")}{" "}
          <b className="text-tx">{counts.closing}</b> · {t("home.upcoming")} <b className="text-tx">{counts.upcoming}</b>
        </p>
        <div className="mt-4 flex gap-2">
          <button
            type="button"
            onClick={() => setMode("time")}
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
            onClick={() => setMode("swipe")}
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

      {mode === "time" && (
        <>
          <div className="pb-7"><FilterChips options={[...STATUS_OPTS, ...EXTRA_OPTS]} active={chips} onToggle={toggle} /></div>

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
            {ongoing.map((e) => <ExhibitionCard key={e.id} exhibition={e} today={today} />)}
          </Section>
        </>
      )}

      {mode === "swipe" && (
        <SwipeDeck items={ongoing} />
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
        <h2 className="mt-2 text-2xl font-extrabold tracking-tight">{bilingual(e.title, e.titleEn)}</h2>
        <div className="mt-2 text-sm text-tx2">
          {e.venue?.name} · {e.startDate}–{e.endDate}
        </div>
      </div>
    </Link>
  );
}
