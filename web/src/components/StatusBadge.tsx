import { ddayLabel } from "@/lib/status";
import type { Exhibition } from "@/lib/catalog";

export function StatusBadge({ e, today }: { e: Exhibition; today?: Date }) {
  if (e.status === "upcoming") {
    return <span className="rounded-full bg-bg/80 px-2 py-1 text-[11px] font-medium text-tx">예정</span>;
  }
  const label = ddayLabel(e.endDate, today);
  if (e.status === "ongoing" && label) {
    return <span className="rounded-full bg-white px-2 py-1 text-[11px] font-bold text-black">{label}</span>;
  }
  return <span className="rounded-full border border-line2 bg-bg/60 px-2 py-1 text-[11px] font-bold text-tx">진행중</span>;
}
