"use client";

// 라벨(상태/그 외/정렬 등) + 칩 줄을 한 그룹으로 묶는 표시 전용 래퍼.
export function FilterGroup({ label, children }: { label?: string; children: React.ReactNode }) {
  return (
    <div className="flex flex-wrap items-center gap-2">
      {label ? <span className="shrink-0 text-[11px] text-tx3">{label}</span> : null}
      {children}
    </div>
  );
}
