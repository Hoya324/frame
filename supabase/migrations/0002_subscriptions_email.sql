-- supabase/migrations/0002_subscriptions_email.sql
-- Subscriptions + email send log for the FRAME notification system.

-- subscriptions: one row per (user, type). filters used only by 'custom'.
create table if not exists public.subscriptions (
  user_id uuid not null references auth.users(id) on delete cascade,
  type text not null check (type in ('weekly_digest', 'closing_soon', 'custom')),
  enabled boolean not null default true,
  filters jsonb not null default '{}'::jsonb,  -- { artists:[], regions:[], genres:[], mediums:[] }
  updated_at timestamptz not null default now(),
  primary key (user_id, type)
);

-- email_log: dedupe + audit. ref scopes a single logical send within a type.
create table if not exists public.email_log (
  user_id uuid not null references auth.users(id) on delete cascade,
  type text not null,
  ref text not null,
  sent_at timestamptz not null default now(),
  primary key (user_id, type, ref)
);

create index if not exists email_log_user_type_idx on public.email_log (user_id, type);

-- RLS. The web app (anon key) only touches the caller's own subscriptions.
-- Jobs use the service role key, which bypasses RLS entirely.
alter table public.subscriptions enable row level security;
alter table public.email_log enable row level security;

drop policy if exists "subs self all" on public.subscriptions;
create policy "subs self all" on public.subscriptions
  for all using (auth.uid() = user_id) with check (auth.uid() = user_id);

-- email_log: users may read their own log; no client writes (jobs write via service role).
drop policy if exists "email_log self read" on public.email_log;
create policy "email_log self read" on public.email_log
  for select using (auth.uid() = user_id);
