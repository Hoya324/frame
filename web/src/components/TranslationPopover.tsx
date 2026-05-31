"use client";
import { useState } from "react";
import { useLang } from "@/components/LanguageProvider";
import { localized, type TrMap } from "@/lib/catalog";

export function TranslationPopover({
  original, tr, field, className,
}: {
  original: string | null | undefined;
  tr: TrMap | undefined;
  field: string;
  className?: string;
}) {
  const { locale, t } = useLang();
  const [open, setOpen] = useState(false);
  const translation = localized(original, tr, locale, field);
  const text = original ?? "";

  if (!translation) return <p className={className}>{text}</p>;

  return (
    <div className="relative">
      <p className={className}>{text}</p>
      <button
        type="button"
        onClick={() => setOpen(true)}
        className="mt-2 rounded-full border border-line2 px-2.5 py-1 text-[11px] text-tx3 hover:bg-panel2"
      >
        {t("tr.showTranslation")}
      </button>
      {open && (
        <div className="mt-2 rounded-lg border border-line bg-panel p-3 shadow-lg">
          <div className="mb-1.5 flex items-center justify-between text-[10px] text-tx3">
            <span>{t("tr.machine")}</span>
            <button type="button" aria-label={t("tr.close")} onClick={() => setOpen(false)}>✕</button>
          </div>
          <p className="whitespace-pre-line text-[13px] leading-relaxed">{translation}</p>
        </div>
      )}
    </div>
  );
}
