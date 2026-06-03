"use client";
import { useLang } from "@/components/LanguageProvider";
import type { SortKey } from "@/lib/sort";
import { EVENTS, track } from "@/lib/analytics";

const KEY_I18N: Record<SortKey, string> = {
  recommended: "sort.recommended",
  closing: "sort.closing",
  recent: "sort.recent",
  nearby: "sort.nearby",
};

// 단일 선택 정렬 칩. 공통 칩 스타일(FilterChips와 동일).
export function SortChips({
  value, options, onChange, disabled, context,
}: {
  value: SortKey;
  options: SortKey[];
  onChange: (key: SortKey) => void;
  disabled?: Partial<Record<SortKey, boolean>>;
  // Page this control lives on, so the sort_change event is attributable.
  context?: string;
}) {
  const { t } = useLang();
  const handle = (k: SortKey) => {
    if (k !== value) track(EVENTS.sortChange, { sort: k, context });
    onChange(k);
  };
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
            onClick={() => handle(k)}
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
