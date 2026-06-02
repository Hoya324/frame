-- supabase/migrations/0004_backfill_profiles.sql
-- Defense-in-depth for the locale-sync bug: ensure every existing auth user has
-- a profiles row. `handle_new_user` (0001) only fires on auth.users INSERT, so
-- any user who signed up before that trigger was applied has no profiles row.
-- Without a row, `update profiles set locale = ... where id = auth.uid()`
-- matches 0 rows and the chosen UI language is silently never persisted.

-- Backfill missing rows (runs as the migration owner, bypassing RLS).
insert into public.profiles (id, email)
  select id, email from auth.users
  on conflict (id) do nothing;

-- Allow a signed-in user to create their own profiles row from the client too,
-- so a future missing-row case can self-heal via upsert. 0001 added self read +
-- self write (update) policies but no insert policy; this completes the set.
drop policy if exists "profiles self insert" on public.profiles;
create policy "profiles self insert" on public.profiles
  for insert with check (auth.uid() = id);
