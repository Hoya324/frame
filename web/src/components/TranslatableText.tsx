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
  const [showOriginal, setShowOriginal] = useState(false);
  const translation = localized(original, tr, locale, field);
  const text = original ?? "";

  // No translation for the current header locale → just the original text.
  if (!translation) return <span className={className}>{text}</span>;

  // Default to the header-language translation; one tap reveals the original.
  return (
    <span className={className}>
      <span className="border-b border-dotted border-tx3">
        {showOriginal ? text : translation}
      </span>
      <button
        type="button"
        aria-pressed={showOriginal}
        onClick={(e) => { e.preventDefault(); e.stopPropagation(); setShowOriginal((v) => !v); }}
        className="ml-1.5 rounded-full border border-line2 px-2 py-0.5 align-middle text-[11px] text-tx3 hover:bg-panel2"
      >
        {showOriginal ? t("tr.showTranslation") : t("tr.showOriginal")}
      </button>
    </span>
  );
}
