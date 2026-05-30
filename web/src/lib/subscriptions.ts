import type { SupabaseClient } from "@supabase/supabase-js";

export type SubType = "weekly_digest" | "closing_soon" | "custom";
export interface CustomFilters {
  artists?: string[];
  regions?: string[];
  genres?: string[];
  mediums?: string[];
}
export interface Subscription {
  type: SubType;
  enabled: boolean;
  filters: CustomFilters;
}
export type SubscriptionMap = Partial<Record<SubType, Subscription>>;

export async function getSubscriptions(client: SupabaseClient, userId: string): Promise<SubscriptionMap> {
  const { data, error } = await client
    .from("subscriptions")
    .select("type, enabled, filters")
    .eq("user_id", userId);
  if (error) throw error;
  const map: SubscriptionMap = {};
  for (const r of data ?? []) {
    map[r.type as SubType] = { type: r.type, enabled: r.enabled, filters: r.filters ?? {} };
  }
  return map;
}

export async function upsertSubscription(
  client: SupabaseClient,
  userId: string,
  type: SubType,
  enabled: boolean,
  filters: CustomFilters = {},
): Promise<void> {
  const { error } = await client
    .from("subscriptions")
    .upsert({ user_id: userId, type, enabled, filters }, { onConflict: "user_id,type" });
  if (error) throw error;
}
