"use client";
import Link from "next/link";
import { PosterImage } from "@/components/PosterImage";
import { StatusBadge } from "@/components/StatusBadge";
import { ScrapButton } from "@/components/ScrapButton";
import { useLang } from "@/components/LanguageProvider";
import { TranslatableText } from "@/components/TranslatableText";
import type { Exhibition } from "@/lib/catalog";
import { sourceLabel } from "@/lib/sources";

export function ExhibitionCard({ exhibition: e, today }: { exhibition: Exhibition; today?: Date }) {
  const { t } = useLang();
  const label = sourceLabel(e.source, e.sourceUrl);
  // For single-venue sources the label is just the venue name again — only
  // show it when it adds information (aggregators like ARTMAP / Tokyo Art Beat).
  const source = label && label !== e.venue?.name ? label : null;
  const meta = [e.medium, e.exhibitionType].filter(Boolean).join(" · ");
  return (
    <Link href={`/exhibitions/${e.id}`} className="group block">
      <div className="relative aspect-[3/4] overflow-hidden rounded-[3px] border border-line">
        <div className="absolute inset-0 transition-transform duration-300 group-hover:scale-[1.04]">
          <PosterImage src={e.posterImageUrl} alt={e.title} />
        </div>
        <div className="absolute right-2.5 top-2.5"><ScrapButton exhibitionId={e.id} /></div>
        <div className="absolute bottom-2.5 left-2.5"><StatusBadge e={e} today={today} /></div>
      </div>
      <div className="pt-2.5">
        <div className="text-[14.5px] font-semibold leading-tight">
          <TranslatableText original={e.title} tr={e.tr} field="title" />
        </div>
        <div className="mt-1 text-[12.5px] text-tx2">
          {e.venue ? (
            <>
              <TranslatableText original={e.venue.name} tr={e.venue.tr} field="name" />
              {e.venue.district ? ` · ${e.venue.district}` : ""}
            </>
          ) : t("common.venueTbd")}
        </div>
        <div className="mt-1.5 text-[11.5px] text-tx3">
          {[meta, source].filter(Boolean).join("  ·  ")}
        </div>
      </div>
    </Link>
  );
}
