import { createClient, type SupabaseClient } from "@supabase/supabase-js";
import { env } from "./env";

export function makeAdminClient(): SupabaseClient {
  return createClient(env.supabaseUrl(), env.supabaseServiceKey(), {
    auth: { persistSession: false, autoRefreshToken: false },
  });
}

export interface Subscriber { userId: string; email: string; filters: Record<string, string[]>; }

/* eslint-disable @typescript-eslint/no-explicit-any */
/**
 * Enabled subscribers of a given type, with their email from profiles.
 * Done as two queries (subscriptions, then profiles by id) and merged in JS:
 * subscriptions and profiles share no direct FK (both reference auth.users),
 * so a PostgREST embed cannot resolve the relationship.
 */
export async function subscribersOf(
  client: SupabaseClient, type: "weekly_digest" | "closing_soon" | "custom",
): Promise<Subscriber[]> {
  const { data: subs, error: subErr } = await client
    .from("subscriptions")
    .select("user_id, filters")
    .eq("type", type)
    .eq("enabled", true);
  if (subErr) throw subErr;
  const rows = subs ?? [];
  if (rows.length === 0) return [];

  const userIds = [...new Set(rows.map((r: any) => r.user_id as string))];
  const { data: profiles, error: profErr } = await client
    .from("profiles")
    .select("id, email")
    .in("id", userIds);
  if (profErr) throw profErr;
  const emailById = new Map<string, string>(
    (profiles ?? []).map((p: any) => [p.id as string, (p.email ?? "") as string]),
  );

  return rows
    .map((r: any): Subscriber => ({
      userId: r.user_id,
      email: emailById.get(r.user_id) ?? "",
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
