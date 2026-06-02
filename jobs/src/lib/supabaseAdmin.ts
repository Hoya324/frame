import { createClient, type SupabaseClient } from "@supabase/supabase-js";
import { env } from "./env";

export function makeAdminClient(): SupabaseClient {
  return createClient(env.supabaseUrl(), env.supabaseServiceKey(), {
    auth: { persistSession: false, autoRefreshToken: false },
  });
}

export type Locale = "ko" | "en" | "ja";
const LOCALES: Locale[] = ["ko", "en", "ja"];

export interface Subscriber {
  userId: string; email: string; filters: Record<string, string[]>; locale: Locale;
}

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
    .select("id, email, locale")
    .in("id", userIds);
  if (profErr) throw profErr;
  const profileById = new Map<string, { email: string; locale: Locale }>(
    (profiles ?? []).map((p: any) => {
      const loc = p.locale as string | null;
      return [p.id as string, {
        email: (p.email ?? "") as string,
        locale: loc && LOCALES.includes(loc as Locale) ? (loc as Locale) : "ko",
      }];
    }),
  );

  return rows
    .map((r: any): Subscriber => {
      const prof = profileById.get(r.user_id);
      return {
        userId: r.user_id,
        email: prof?.email ?? "",
        filters: r.filters ?? {},
        locale: prof?.locale ?? "ko",
      };
    })
    .filter((s: Subscriber) => s.email);
}

/** Exhibition ids a user has scrapped. */
export async function bookmarksOf(client: SupabaseClient, userId: string): Promise<string[]> {
  const { data, error } = await client.from("bookmarks").select("exhibition_id").eq("user_id", userId);
  if (error) throw error;
  return (data ?? []).map((r: { exhibition_id: string }) => r.exhibition_id);
}
