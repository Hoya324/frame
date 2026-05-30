import { createClient, type SupabaseClient } from "@supabase/supabase-js";
import { env } from "./env";

export function makeAdminClient(): SupabaseClient {
  return createClient(env.supabaseUrl(), env.supabaseServiceKey(), {
    auth: { persistSession: false, autoRefreshToken: false },
  });
}

export interface Subscriber { userId: string; email: string; filters: Record<string, string[]>; }

/* eslint-disable @typescript-eslint/no-explicit-any */
/** Enabled subscribers of a given type, joined to their email from profiles. */
export async function subscribersOf(
  client: SupabaseClient, type: "weekly_digest" | "closing_soon" | "custom",
): Promise<Subscriber[]> {
  const { data, error } = await client
    .from("subscriptions")
    .select("user_id, filters, profiles!inner(email)")
    .eq("type", type)
    .eq("enabled", true);
  if (error) throw error;
  return (data ?? [])
    .map((r: any) => ({
      userId: r.user_id,
      email: r.profiles?.email ?? "",
      filters: r.filters ?? {},
    }))
    .filter((s: Subscriber) => s.email);
}

/** Exhibition ids a user has scrapped. */
export async function bookmarksOf(client: SupabaseClient, userId: string): Promise<string[]> {
  const { data, error } = await client.from("bookmarks").select("exhibition_id").eq("user_id", userId);
  if (error) throw error;
  return (data ?? []).map((r: { exhibition_id: string }) => r.exhibition_id);
}
