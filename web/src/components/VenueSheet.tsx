"use client";
import { useEffect, useState } from "react";
import { X } from "lucide-react";
import { ExhibitionCard } from "@/components/ExhibitionCard";
import { TranslatableText } from "@/components/TranslatableText";
import { useLang } from "@/components/LanguageProvider";
import { venueSummary, sortForSheet, nextSnap, type SortMode } from "@/lib/venueSheet";
import type { Exhibition, VenueEmbed } from "@/lib/catalog";

const SORTS: { mode: SortMode; key: string }[] = [
  { mode: "ongoing", key: "venue.sortOngoing" },
  { mode: "closing", key: "venue.sortClosing" },
  { mode: "recent", key: "venue.sortRecent" },
];

export function VenueSheet({
  venue, exhibitions, onClose,
}: {
  venue: VenueEmbed;
  exhibitions: Exhibition[];
  onClose: () => void;
}) {
  const { t } = useLang();
  const [sort, setSort] = useState<SortMode>("ongoing");
  const [snap, setSnap] = useState<"full" | "peek">("full");
  const [dragY, setDragY] = useState(0);
  const [startY, setStartY] = useState<number | null>(null);

  // 다른 venue가 열리면 시트를 처음 상태로 리셋. (렌더 중 파생 상태 패턴으로,
  // effect 내 setState 없이 prop 변경에 동기적으로 반응한다.)
  const [prevVenueId, setPrevVenueId] = useState(venue.id);
  if (prevVenueId !== venue.id) {
    setPrevVenueId(venue.id);
    setSort("ongoing");
    setSnap("full");
    setDragY(0);
    setStartY(null);
  }

  // Esc로 닫기.
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => { if (e.key === "Escape") onClose(); };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [onClose]);

  // 시트는 전체 화면을 덮는 모달이므로 열려 있는 동안 뒤 페이지 스크롤을 잠근다.
  useEffect(() => {
    const prev = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    return () => { document.body.style.overflow = prev; };
  }, []);

  const summary = venueSummary(exhibitions);
  const sorted = sortForSheet(exhibitions, sort);

  const onPointerDown = (e: React.PointerEvent) => {
    setStartY(e.clientY);
    (e.currentTarget as HTMLElement).setPointerCapture(e.pointerId);
  };
  const onPointerMove = (e: React.PointerEvent) => {
    if (startY === null) return;
    setDragY(Math.max(0, e.clientY - startY));
  };
  const onPointerUp = (e: React.PointerEvent) => {
    if (startY === null) return;
    const target = nextSnap(snap, e.clientY - startY);
    setStartY(null);
    setDragY(0);
    if (target === "closed") onClose();
    else setSnap(target);
  };

  const basePct = snap === "full" ? 0 : 45;

  return (
    <div className="fixed inset-0 z-[60]" role="dialog" aria-modal="true">
      <button
        type="button"
        aria-label={t("venue.close")}
        onClick={onClose}
        className="absolute inset-0 bg-black/50 md:bg-black/30"
      />
      <div
        className="absolute inset-x-0 bottom-0 flex max-h-[88vh] flex-col rounded-t-2xl border border-line bg-bg shadow-[0_-8px_40px_rgba(0,0,0,0.6)] transition-transform duration-200 md:inset-y-0 md:left-auto md:right-0 md:max-h-none md:w-[400px] md:rounded-none md:border-l md:!translate-y-0"
        style={{ transform: `translateY(calc(${basePct}% + ${dragY}px))` }}
      >
        {/* 모바일 드래그 핸들 */}
        <div
          className="flex shrink-0 cursor-grab touch-none justify-center py-2.5 md:hidden"
          onPointerDown={onPointerDown}
          onPointerMove={onPointerMove}
          onPointerUp={onPointerUp}
        >
          <span className="h-1.5 w-10 rounded-full bg-line2" />
        </div>

        {/* 헤더 */}
        <div className="shrink-0 border-b border-line px-5 pb-3 pt-1 md:pt-5">
          <div className="flex items-start gap-3">
            <div className="min-w-0 flex-1">
              <h2 className="truncate text-[18px] font-bold leading-tight">
                <TranslatableText original={venue.name} tr={venue.tr} field="name" />
              </h2>
              <div className="mt-1 text-[12.5px] text-tx2">
                {[venue.region, venue.district].filter(Boolean).join(" · ")}
              </div>
              <div data-testid="venue-summary" className="mt-1.5 text-[12px] text-tx3">
                {t("venue.exhibitions")} <b className="text-tx">{summary.total}</b>
                {summary.ongoing > 0 ? ` · ${t("filter.ongoing")} ${summary.ongoing}` : ""}
                {summary.upcoming > 0 ? ` · ${t("filter.upcoming")} ${summary.upcoming}` : ""}
              </div>
            </div>
            <button
              type="button"
              onClick={onClose}
              aria-label={t("venue.close")}
              className="hidden rounded-full p-1.5 text-tx2 transition hover:bg-line md:block"
            >
              <X size={18} />
            </button>
          </div>

          {/* 정렬 칩 */}
          <div className="mt-3 flex gap-2">
            {SORTS.map((s) => (
              <button
                key={s.mode}
                type="button"
                onClick={() => setSort(s.mode)}
                aria-pressed={sort === s.mode}
                className={`rounded-full px-3 py-1 text-xs font-semibold transition ${
                  sort === s.mode ? "bg-white text-black" : "border border-line2 text-tx2"
                }`}
              >
                {t(s.key)}
              </button>
            ))}
          </div>
        </div>

        {/* 포스터 2열 그리드 */}
        <div className="grid grid-cols-2 gap-4 overflow-y-auto p-5">
          {sorted.map((e) => (
            <ExhibitionCard key={e.id} exhibition={e} />
          ))}
        </div>
      </div>
    </div>
  );
}
