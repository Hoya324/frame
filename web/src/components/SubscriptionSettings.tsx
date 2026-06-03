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
import { useLang } from "@/components/LanguageProvider";

const ROWS: { type: SubType; labelKey: string; descKey: string }[] = [
  { type: "weekly_digest", labelKey: "sub.weekly", descKey: "sub.weeklyDesc" },
  { type: "closing_soon", labelKey: "sub.closing", descKey: "sub.closingDesc" },
  { type: "custom", labelKey: "sub.custom", descKey: "sub.customDesc" },
];

export function SubscriptionSettings() {
  const { user, signIn } = useAuth();
  const { t } = useLang();
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
    if (!user) { await signIn(); return; }
    const prev = subs[type];
    const filters = prev?.filters ?? {};
    setSubs((s) => ({ ...s, [type]: { type, enabled, filters } }));
    await upsertSubscription(getSupabase(), user.id, type, enabled, filters);
  }

  async function setFilters(type: SubType, filters: CustomFilters) {
    if (!user) { await signIn(); return; }
    const enabled = subs[type]?.enabled ?? true;
    setSubs((s) => ({ ...s, [type]: { type, enabled, filters } }));
    await upsertSubscription(getSupabase(), user.id, type, enabled, filters);
  }

  const custom = subs.custom;
  const toggleFilter = (key: keyof CustomFilters, value: string) => {
    const cur = custom?.filters[key] ?? [];
    const next = cur.includes(value) ? cur.filter((v) => v !== value) : [...cur, value];
    void setFilters("custom", { ...(custom?.filters ?? {}), [key]: next });
  };

  return (
    <div className="rounded-lg border border-line p-5">
      <div className="text-sm text-tx3">{t("sub.title")}</div>
      {!user && (
        <button
          type="button"
          onClick={() => void signIn()}
          className="mt-3 flex w-full items-center justify-between rounded-md border border-line2 bg-panel2 px-3.5 py-2.5 text-left text-sm text-tx2 hover:text-tx"
        >
          <span>{t("sub.loginBanner")}</span>
          <span className="ml-3 shrink-0 font-semibold text-tx">{t("common.signIn")}</span>
        </button>
      )}
      <div className="mt-4 space-y-4">
        {ROWS.map((row) => {
          const on = subs[row.type]?.enabled ?? false;
          const label = t(row.labelKey);
          return (
            <div key={row.type}>
              <div className="flex items-center justify-between">
                <div>
                  <div className="text-sm font-medium">{label}</div>
                  <div className="text-xs text-tx3">{t(row.descKey)}</div>
                </div>
                <button
                  role="switch" aria-checked={on} aria-label={label}
                  onClick={() => void setEnabled(row.type, !on)}
                  disabled={!!user && !loaded}
                  className={`relative h-6 w-11 rounded-full transition ${on ? "bg-white" : "bg-panel2 border border-line"}`}
                >
                  <span className={`absolute top-0.5 h-5 w-5 rounded-full transition ${on ? "left-[22px] bg-black" : "left-0.5 bg-tx2"}`} />
                </button>
              </div>
              {row.type === "custom" && on && (
                <div className="mt-3 space-y-2 pl-1">
                  <div className="text-xs text-tx3">{t("sub.region")}</div>
                  <FilterChips options={regions.map((r) => ({ value: r, label: r }))}
                    active={custom?.filters.regions ?? []} onToggle={(v) => toggleFilter("regions", v)} />
                  <div className="text-xs text-tx3">{t("sub.medium")}</div>
                  <FilterChips
                    options={[{ value: "photo", label: t("filter.photo") }, { value: "video", label: t("filter.video") }, { value: "gear", label: t("filter.gear") }]}
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
