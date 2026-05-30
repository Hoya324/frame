import type { SupabaseClient } from "@supabase/supabase-js";

export async function loadSentRefs(
  client: SupabaseClient, userId: string, type: string,
): Promise<Set<string>> {
  const { data, error } = await client
    .from("email_log").select("ref").eq("user_id", userId).eq("type", type);
  if (error) throw error;
  return new Set((data ?? []).map((r: { ref: string }) => r.ref));
}

export async function recordSent(
  client: SupabaseClient, userId: string, type: string, refs: string[],
): Promise<void> {
  if (refs.length === 0) return;
  const { error } = await client
    .from("email_log").insert(refs.map((ref) => ({ user_id: userId, type, ref })));
  if (error) throw error;
}
