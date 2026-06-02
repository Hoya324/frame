"use client";
import { useLang } from "@/components/LanguageProvider";
import type { SortKey } from "@/lib/sort";

const KEY_I18N: Record<SortKey, string> = {
  recommended: "sort.recommended",
  closing: "sort.closing",
  recent: "sort.recent",
  nearby: "sort.nearby",
};

// 단일 선택 정렬 칩. 공통 칩 스타일(FilterChips와 동일).
export function SortChips({
  value, options, onChange, disabled,
}: {
  value: SortKey;
  options: SortKey[];
  onChange: (key: SortKey) => void;
  disabled?: Partial<Record<SortKey, boolean>>;
}) {
  const { t } = useLang();
  return (
    <div className="flex flex-wrap gap-2">
      {options.map((k) => {
        const on = value === k;
        const off = disabled?.[k];
        return (
          <button
            key={k}
            type="button"
            disabled={off}
            onClick={() => onChange(k)}
            aria-pressed={on}
            className={`rounded-full px-3.5 py-1.5 text-[13px] font-medium transition disabled:opacity-40 ${
              on ? "border border-white bg-white font-semibold text-black"
                 : "border border-line text-tx2 hover:text-tx"
            }`}
          >
            {t(KEY_I18N[k])}
          </button>
        );
      })}
    </div>
  );
}
