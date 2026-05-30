"use client";
import { useEffect, useMemo, useState } from "react";
import { getSupabase } from "@/lib/supabase";
import { useAuth } from "@/components/AuthProvider";
import {
  getSubscriptions, upsertSubscription,
  type CustomFilters, type SubscriptionMap, type SubType,
} from "@/lib/subscriptions";
import { loadCatalogSync } from "@/lib/catalogClient";
import { FilterChips } from "@/components/FilterChips";

const ROWS: { type: SubType; label: string; desc: string }[] = [
  { type: "weekly_digest", label: "주간 다이제스트", desc: "매주 새로/진행 중인 전시 모음" },
  { type: "closing_soon", label: "종료 임박 알림", desc: "스크랩한 전시가 곧 끝날 때 (D-3, D-1)" },
  { type: "custom", label: "맞춤 알림", desc: "관심 조건에 맞는 새 전시" },
];

export function SubscriptionSettings() {
  const { user } = useAuth();
  const catalog = loadCatalogSync();
  const [subs, setSubs] = useState<SubscriptionMap>({});
  const [loaded, setLoaded] = useState(false);

  useEffect(() => {
    if (!user) return;
    let active = true;
    getSubscriptions(getSupabase(), user.id)
      .then((m) => { if (active) { setSubs(m); setLoaded(true); } })
      .catch(() => { if (active) setLoaded(true); });
    return () => { active = false; };
  }, [user]);

  const regions = useMemo(
    () => Array.from(new Set(catalog.venues.map((v) => v.region).filter(Boolean))) as string[],
    [catalog.venues],
  );

  async function setEnabled(type: SubType, enabled: boolean) {
    const prev = subs[type];
    const filters = prev?.filters ?? {};
    setSubs((s) => ({ ...s, [type]: { type, enabled, filters } }));
    if (user) await upsertSubscription(getSupabase(), user.id, type, enabled, filters);
  }

  async function setFilters(type: SubType, filters: CustomFilters) {
    const enabled = subs[type]?.enabled ?? true;
    setSubs((s) => ({ ...s, [type]: { type, enabled, filters } }));
    if (user) await upsertSubscription(getSupabase(), user.id, type, enabled, filters);
  }

  if (!user) return null;

  const custom = subs.custom;
  const toggleFilter = (key: keyof CustomFilters, value: string) => {
    const cur = custom?.filters[key] ?? [];
    const next = cur.includes(value) ? cur.filter((v) => v !== value) : [...cur, value];
    void setFilters("custom", { ...(custom?.filters ?? {}), [key]: next });
  };

  return (
    <div className="rounded-lg border border-line p-5">
      <div className="text-sm text-tx3">구독 설정</div>
      <div className="mt-4 space-y-4">
        {ROWS.map((row) => {
          const on = subs[row.type]?.enabled ?? false;
          return (
            <div key={row.type}>
              <div className="flex items-center justify-between">
                <div>
                  <div className="text-sm font-medium">{row.label}</div>
                  <div className="text-xs text-tx3">{row.desc}</div>
                </div>
                <button
                  role="switch" aria-checked={on} aria-label={row.label}
                  onClick={() => void setEnabled(row.type, !on)}
                  disabled={!loaded}
                  className={`relative h-6 w-11 rounded-full transition ${on ? "bg-white" : "bg-panel2 border border-line"}`}
                >
                  <span className={`absolute top-0.5 h-5 w-5 rounded-full transition ${on ? "left-[22px] bg-black" : "left-0.5 bg-tx2"}`} />
                </button>
              </div>
              {row.type === "custom" && on && (
                <div className="mt-3 space-y-2 pl-1">
                  <div className="text-xs text-tx3">지역</div>
                  <FilterChips options={regions.map((r) => ({ value: r, label: r }))}
                    active={custom?.filters.regions ?? []} onToggle={(v) => toggleFilter("regions", v)} />
                  <div className="text-xs text-tx3">매체</div>
                  <FilterChips
                    options={[{ value: "photo", label: "사진" }, { value: "video", label: "영상" }, { value: "gear", label: "장비" }]}
                    active={custom?.filters.mediums ?? []} onToggle={(v) => toggleFilter("mediums", v)} />
                </div>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}
