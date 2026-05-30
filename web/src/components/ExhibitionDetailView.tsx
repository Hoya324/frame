"use client";
import { PosterImage } from "@/components/PosterImage";
import { ScrapButton } from "@/components/ScrapButton";
import { StatusBadge } from "@/components/StatusBadge";
import { useLang } from "@/components/LanguageProvider";
import type { Exhibition } from "@/lib/catalog";

export function ExhibitionDetailView({ e }: { e: Exhibition }) {
  const { t } = useLang();
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
          <h1 className="mt-3 text-3xl font-extrabold tracking-tight">{e.title}</h1>
          {e.titleEn && <div className="mt-1 text-tx2">{e.titleEn}</div>}
          <div className="mt-5 space-y-1.5 text-sm">
            <div><span className="text-tx3">{t("detail.venue")}</span>  {e.venue?.name ?? t("common.tbd")}{e.venue?.district ? ` · ${e.venue.district}` : ""}</div>
            <div className="flex items-center gap-2"><span><span className="text-tx3">{t("detail.period")}</span>  {e.startDate} – {e.endDate}</span><StatusBadge e={e} /></div>
            <div><span className="text-tx3">{t("detail.fee")}</span>  {price}</div>
            {e.artists.length > 0 && <div><span className="text-tx3">{t("detail.artists")}</span>  {e.artists.map((a) => a.name).join(", ")}</div>}
            {e.openHours && <div><span className="text-tx3">{t("detail.hours")}</span>  {e.openHours}</div>}
          </div>
          {e.description && <p className="mt-6 whitespace-pre-line text-[14px] leading-relaxed text-tx2">{e.description}</p>}
          <div className="mt-7 flex items-center gap-3">
            <ScrapButton exhibitionId={e.id} />
            {e.sourceUrl && (
              <a href={e.sourceUrl} target="_blank" rel="noopener noreferrer"
                className="rounded-lg border border-line2 px-4 py-2 text-sm font-medium hover:bg-panel2">
                {t("detail.source")}
              </a>
            )}
          </div>
        </div>
      </div>
    </main>
  );
}
