"use client";
import { useState } from "react";
import { useLang } from "@/components/LanguageProvider";
import { localized, type TrMap } from "@/lib/catalog";

export function TranslatableText({
  original, tr, field, className,
}: {
  original: string | null | undefined;
  tr: TrMap | undefined;
  field: string;
  className?: string;
}) {
  const { locale, t } = useLang();
  const [showTr, setShowTr] = useState(false);
  const translation = localized(original, tr, locale, field);
  const text = original ?? "";

  if (!translation) return <span className={className}>{text}</span>;

  return (
    <span className={className}>
      <span className="border-b border-dotted border-tx3">
        {showTr ? translation : text}
      </span>
      <button
        type="button"
        onClick={(e) => { e.preventDefault(); e.stopPropagation(); setShowTr((v) => !v); }}
        className="ml-1.5 rounded-full border border-line2 px-1.5 py-0.5 align-middle text-[9.5px] text-tx3 hover:bg-panel2"
      >
        {showTr ? t("tr.showOriginal") : t("tr.showTranslation")}
      </button>
    </span>
  );
}
