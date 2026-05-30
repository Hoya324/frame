"use client";
import { ddayLabel } from "@/lib/status";
import { useLang } from "@/components/LanguageProvider";
import type { Exhibition } from "@/lib/catalog";

export function StatusBadge({ e, today }: { e: Exhibition; today?: Date }) {
  const { t } = useLang();
  if (e.status === "upcoming") {
    return <span className="rounded-full bg-bg/80 px-2 py-1 text-[11px] font-medium text-tx">{t("filter.upcoming")}</span>;
  }
  if (e.status === "past") {
    return <span className="rounded-full border border-line2 bg-bg/60 px-2 py-1 text-[11px] font-medium text-tx3">{t("filter.past")}</span>;
  }
  if (e.status !== "ongoing") return null;
  const label = ddayLabel(e.endDate, today);
  if (label) {
    return <span className="rounded-full bg-white px-2 py-1 text-[11px] font-bold text-black">{label}</span>;
  }
  return <span className="rounded-full border border-line2 bg-bg/60 px-2 py-1 text-[11px] font-bold text-tx">{t("filter.ongoing")}</span>;
}
