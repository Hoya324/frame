"use client";
import { useEffect, useState } from "react";
import dynamic from "next/dynamic";
import { PosterImage } from "@/components/PosterImage";
import { ScrapButton } from "@/components/ScrapButton";
import { StatusBadge } from "@/components/StatusBadge";
import { useLang } from "@/components/LanguageProvider";
import { inLocale, type Exhibition } from "@/lib/catalog";
import { LOCALES, LOCALE_LABEL, translate, type Locale } from "@/lib/i18n";
import { sourceLabel } from "@/lib/sources";
import { EVENTS, track } from "@/lib/analytics";

// maplibre-gl touches `window`, so the venue mini-map is client-only.
const MapView = dynamic(() => import("@/components/MapView").then((m) => m.MapView), { ssr: false });

export function ExhibitionDetailView({ e }: { e: Exhibition }) {
  const { locale } = useLang();
  // Content language for this page: defaults to the header locale, can be
  // switched independently with the picker, and re-syncs when the header
  // changes (React's "adjust state during render" pattern — no effect needed).
  const [lang, setLang] = useState<Locale>(locale);
  const [prevLocale, setPrevLocale] = useState<Locale>(locale);
  if (locale !== prevLocale) {
    setPrevLocale(locale);
    setLang(locale);
  }
  // The whole page (labels + content) follows the picked language, so the
  // selection gives a coherent single-language view of the exhibition.
  const t = (key: string) => translate(lang, key);

  // One view event per exhibition opened (re-fires if the user navigates to a
  // different exhibition without a full remount).
  useEffect(() => {
    track(EVENTS.exhibitionView, {
      exhibition_id: e.id,
      title: e.title,
      venue: e.venue?.name,
      status: e.status,
      medium: e.medium,
      source: e.source,
    });
  }, [e.id, e.title, e.venue?.name, e.status, e.medium, e.source]);

  const source = sourceLabel(e.source, e.sourceUrl);
  const price =
    e.feeType === "free"
      ? t("common.free")
      : e.priceMin
        ? `₩${e.priceMin.toLocaleString()}~`
        : t("common.paid");

  const title = inLocale(e.title, e.tr, lang, "title");
  const description = e.description ? inLocale(e.description, e.tr, lang, "description") : "";

  const venueName = e.venue ? inLocale(e.venue.name, e.venue.tr, lang, "name") : "";
  const hasCoords = e.venue?.lat != null && e.venue?.lng != null;
  // Google Maps Universal URL — lat,lng as destination lands on the exact point
  // regardless of locale or place-name ambiguity. travelmode=transit suits the
  // mostly-urban exhibition venues; users can switch modes inside Google Maps.
  const directionsUrl = hasCoords
    ? `https://www.google.com/maps/dir/?api=1&destination=${e.venue!.lat},${e.venue!.lng}&travelmode=transit`
    : null;

  return (
    <main className="mx-auto max-w-[1100px] px-7 py-8">
      <div className="grid gap-8 md:grid-cols-[420px_1fr]">
        <div className="relative aspect-[3/4] overflow-hidden rounded border border-line">
          <PosterImage src={e.posterImageUrl} alt={e.title} />
        </div>
        <div>
          {/* Per-page content language: KO / EN / JA, defaulting to the header. */}
          <div className="mb-4 inline-flex rounded-lg border border-line2 p-0.5 text-[12.5px]" role="group" aria-label={t("detail.language")}>
            {LOCALES.map((l) => (
              <button
                key={l}
                type="button"
                aria-pressed={l === lang}
                onClick={() => setLang(l)}
                className={`rounded-md px-2.5 py-1 transition ${
                  l === lang ? "bg-white font-semibold text-black" : "text-tx2 hover:text-tx"
                }`}
              >
                {LOCALE_LABEL[l]}
              </button>
            ))}
          </div>
          <div className="text-[11px] font-semibold uppercase tracking-widest text-tx3">
            {[e.medium, e.exhibitionType].filter(Boolean).join(" · ")}
          </div>
          <h1 className="mt-3 text-3xl font-extrabold tracking-tight">{title}</h1>
          <div className="mt-5 space-y-1.5 text-sm">
            <div><span className="text-tx3">{t("detail.venue")}</span>  {e.venue ? inLocale(e.venue.name, e.venue.tr, lang, "name") : t("common.tbd")}{e.venue?.district ? ` · ${e.venue.district}` : ""}</div>
            <div className="flex items-center gap-2"><span><span className="text-tx3">{t("detail.period")}</span>  {e.startDate} – {e.endDate}</span><StatusBadge e={e} /></div>
            <div><span className="text-tx3">{t("detail.fee")}</span>  {price}</div>
            {e.artists.length > 0 && <div><span className="text-tx3">{t("detail.artists")}</span>  {e.artists.map((a, i) => (
              <span key={a.id}>
                {i > 0 ? ", " : ""}
                {inLocale(a.name, a.tr, lang, "name")}
              </span>
            ))}</div>}
            {e.openHours && <div><span className="text-tx3">{t("detail.hours")}</span>  {e.openHours}</div>}
          </div>
          {description && (
            <p className="mt-6 whitespace-pre-line text-[14px] leading-relaxed text-tx2">{description}</p>
          )}
          {source && (
            <div className="mt-6 text-[12.5px] text-tx3">
              {t("detail.from")} <span className="text-tx2">{source}</span>
            </div>
          )}
          <div className="mt-3 flex items-center gap-3">
            <ScrapButton exhibitionId={e.id} />
            {e.sourceUrl && (
              <a href={e.sourceUrl} target="_blank" rel="noopener noreferrer"
                onClick={() => track(EVENTS.sourceLinkClick, { exhibition_id: e.id, source: e.source })}
                aria-label={source ? `${t("detail.from")} ${source}` : t("detail.source")}
                className="inline-flex items-center gap-1 rounded-lg border border-line2 px-4 py-2 text-sm font-medium hover:bg-panel2">
                {source ?? t("detail.source")}
                <span aria-hidden className="text-tx3">↗</span>
              </a>
            )}
          </div>
        </div>
      </div>

      {hasCoords && (
        <section className="mt-10">
          <div className="mb-3 flex flex-wrap items-center justify-between gap-3">
            <h2 className="text-sm font-semibold uppercase tracking-widest text-tx3">
              {t("detail.location")}
            </h2>
            <a
              href={directionsUrl!}
              target="_blank"
              rel="noopener noreferrer"
              onClick={() =>
                track(EVENTS.directionsClick, {
                  exhibition_id: e.id,
                  venue_id: e.venue?.id,
                })
              }
              className="inline-flex items-center gap-1 rounded-lg border border-line2 px-4 py-2 text-sm font-medium hover:bg-panel2"
            >
              {t("detail.directions")}
              <span aria-hidden className="text-tx3">↗</span>
            </a>
          </div>
          <MapView items={[e]} height={320} />
          <div className="mt-2 text-[12.5px] text-tx3">
            {venueName}
            {e.venue?.district ? ` · ${e.venue.district}` : ""}
          </div>
        </section>
      )}
    </main>
  );
}
