"use client";
import { PosterImage } from "@/components/PosterImage";
import { ScrapButton } from "@/components/ScrapButton";
import { StatusBadge } from "@/components/StatusBadge";
import { TranslatableText } from "@/components/TranslatableText";
import { TranslationPopover } from "@/components/TranslationPopover";
import { useLang } from "@/components/LanguageProvider";
import type { Exhibition } from "@/lib/catalog";
import { sourceLabel } from "@/lib/sources";

export function ExhibitionDetailView({ e }: { e: Exhibition }) {
  const { t } = useLang();
  const source = sourceLabel(e.source, e.sourceUrl);
  const price =
    e.feeType === "free"
      ? t("common.free")
      : e.priceMin
        ? `₩${e.priceMin.toLocaleString()}~`
        : t("common.paid");
  return (
    <main className="mx-auto max-w-[1100px] px-7 py-8">
      <div className="grid gap-8 md:grid-cols-[420px_1fr]">
        <div className="relative aspect-[3/4] overflow-hidden rounded border border-line">
          <PosterImage src={e.posterImageUrl} alt={e.title} />
        </div>
        <div>
          <div className="text-[11px] font-semibold uppercase tracking-widest text-tx3">
            {[e.medium, e.exhibitionType].filter(Boolean).join(" · ")}
          </div>
          <h1 className="mt-3 text-3xl font-extrabold tracking-tight">
            <TranslatableText original={e.title} tr={e.tr} field="title" />
          </h1>
          <div className="mt-5 space-y-1.5 text-sm">
            <div><span className="text-tx3">{t("detail.venue")}</span>  {e.venue ? <TranslatableText original={e.venue.name} tr={e.venue.tr} field="name" /> : t("common.tbd")}{e.venue?.district ? ` · ${e.venue.district}` : ""}</div>
            <div className="flex items-center gap-2"><span><span className="text-tx3">{t("detail.period")}</span>  {e.startDate} – {e.endDate}</span><StatusBadge e={e} /></div>
            <div><span className="text-tx3">{t("detail.fee")}</span>  {price}</div>
            {e.artists.length > 0 && <div><span className="text-tx3">{t("detail.artists")}</span>  {e.artists.map((a, i) => (
              <span key={a.id}>
                {i > 0 ? ", " : ""}
                <TranslatableText original={a.name} tr={a.tr} field="name" />
              </span>
            ))}</div>}
            {e.openHours && <div><span className="text-tx3">{t("detail.hours")}</span>  {e.openHours}</div>}
          </div>
          {e.description && (
            <TranslationPopover
              original={e.description}
              tr={e.tr}
              field="description"
              className="mt-6 whitespace-pre-line text-[14px] leading-relaxed text-tx2"
            />
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
                aria-label={source ? `${t("detail.from")} ${source}` : t("detail.source")}
                className="inline-flex items-center gap-1 rounded-lg border border-line2 px-4 py-2 text-sm font-medium hover:bg-panel2">
                {source ?? t("detail.source")}
                <span aria-hidden className="text-tx3">↗</span>
              </a>
            )}
          </div>
        </div>
      </div>
    </main>
  );
}
