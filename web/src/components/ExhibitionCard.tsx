import Link from "next/link";
import { PosterImage } from "@/components/PosterImage";
import { StatusBadge } from "@/components/StatusBadge";
import { ScrapButton } from "@/components/ScrapButton";
import type { Exhibition } from "@/lib/catalog";

export function ExhibitionCard({ exhibition: e, today }: { exhibition: Exhibition; today?: Date }) {
  return (
    <Link href={`/exhibitions/${e.id}`} className="group block">
      <div className="relative aspect-[3/4] overflow-hidden rounded-[3px] border border-line">
        <PosterImage src={e.posterImageUrl} alt={e.title} />
        <div className="absolute right-2.5 top-2.5"><ScrapButton exhibitionId={e.id} /></div>
        <div className="absolute bottom-2.5 left-2.5"><StatusBadge e={e} today={today} /></div>
      </div>
      <div className="pt-2.5">
        <div className="text-[14.5px] font-semibold leading-tight">{e.title}</div>
        <div className="mt-1 text-[12.5px] text-tx2">
          {e.venue ? `${e.venue.name}${e.venue.district ? ` · ${e.venue.district}` : ""}` : "장소 미정"}
        </div>
        <div className="mt-1.5 text-[11.5px] text-tx3">
          {[e.medium, e.exhibitionType].filter(Boolean).join(" · ")}
        </div>
      </div>
    </Link>
  );
}
