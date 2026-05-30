import type { SupabaseClient } from "@supabase/supabase-js";

export async function listBookmarkIds(client: SupabaseClient, userId: string): Promise<Set<string>> {
  const { data, error } = await client.from("bookmarks").select("exhibition_id").eq("user_id", userId);
  if (error) throw error;
  return new Set((data ?? []).map((r: { exhibition_id: string }) => r.exhibition_id));
}

export async function addBookmark(client: SupabaseClient, userId: string, exhibitionId: string): Promise<void> {
  const { error } = await client.from("bookmarks").insert({ user_id: userId, exhibition_id: exhibitionId });
  if (error) throw error;
}

export async function removeBookmark(client: SupabaseClient, userId: string, exhibitionId: string): Promise<void> {
  const { error } = await client.from("bookmarks").delete().eq("user_id", userId).eq("exhibition_id", exhibitionId);
  if (error) throw error;
}
