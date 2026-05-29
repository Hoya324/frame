import { notFound } from "next/navigation";
import { loadCatalog } from "@/lib/catalog";
import { PosterImage } from "@/components/PosterImage";
import { ScrapButton } from "@/components/ScrapButton";
import { ddayLabel } from "@/lib/status";

export async function generateStaticParams() {
  const cat = await loadCatalog();
  return cat.exhibitions.map((e) => ({ id: e.id }));
}

export default async function ExhibitionDetail({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  const cat = await loadCatalog();
  const e = cat.exhibitions.find((x) => x.id === id);
  if (!e) notFound();

  const dday = ddayLabel(e.endDate);
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
            <div><span className="text-tx3">장소</span>  {e.venue?.name ?? "미정"}{e.venue?.district ? ` · ${e.venue.district}` : ""}</div>
            <div><span className="text-tx3">기간</span>  {e.startDate} – {e.endDate} {dday && <span className="ml-2 rounded-full bg-white px-2 py-0.5 text-[11px] font-bold text-black">{dday}</span>}</div>
            <div><span className="text-tx3">요금</span>  {e.feeType === "free" ? "무료" : e.priceMin ? `${e.priceMin.toLocaleString()}원~` : "유료"}</div>
            {e.artists.length > 0 && <div><span className="text-tx3">작가</span>  {e.artists.map((a) => a.name).join(", ")}</div>}
            {e.openHours && <div><span className="text-tx3">관람</span>  {e.openHours}</div>}
          </div>
          {e.description && <p className="mt-6 whitespace-pre-line text-[14px] leading-relaxed text-tx2">{e.description}</p>}
          <div className="mt-7 flex items-center gap-3">
            <ScrapButton />
            {e.sourceUrl && (
              <a href={e.sourceUrl} target="_blank" rel="noopener noreferrer"
                className="rounded-lg border border-line2 px-4 py-2 text-sm font-medium hover:bg-panel2">
                원문 보기
              </a>
            )}
          </div>
        </div>
      </div>
    </main>
  );
}
