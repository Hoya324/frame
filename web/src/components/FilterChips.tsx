"use client";

export interface ChipOption { value: string; label: string; }

export function FilterChips({
  options, active, onToggle,
}: { options: ChipOption[]; active: string[]; onToggle: (value: string) => void }) {
  return (
    <div className="flex flex-wrap gap-2">
      {options.map((o) => {
        const on = active.includes(o.value);
        return (
          <button key={o.value} type="button" onClick={() => onToggle(o.value)}
            className={`rounded-full px-3.5 py-1.5 text-[13px] font-medium transition ${
              on ? "border border-white bg-white font-semibold text-black"
                 : "border border-line text-tx2 hover:text-tx"}`}>
            {o.label}
          </button>
        );
      })}
    </div>
  );
}
