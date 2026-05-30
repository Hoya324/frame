-- supabase/migrations/0001_user_plane.sql
-- User plane for the FRAME discovery app: profiles + bookmarks, RLS-protected.

-- profiles: one row per auth user.
create table if not exists public.profiles (
  id uuid primary key references auth.users(id) on delete cascade,
  email text,
  created_at timestamptz not null default now()
);

-- bookmarks (scrap): a user's saved exhibitions. exhibition_id is the catalog id (string).
create table if not exists public.bookmarks (
  user_id uuid not null references auth.users(id) on delete cascade,
  exhibition_id text not null,
  created_at timestamptz not null default now(),
  primary key (user_id, exhibition_id)
);

create index if not exists bookmarks_user_idx on public.bookmarks (user_id, created_at desc);

-- Auto-create a profile row when a new auth user signs up.
create or replace function public.handle_new_user()
returns trigger
language plpgsql
security definer set search_path = public
as $$
begin
  insert into public.profiles (id, email)
  values (new.id, new.email)
  on conflict (id) do nothing;
  return new;
end;
$$;

drop trigger if exists on_auth_user_created on auth.users;
create trigger on_auth_user_created
  after insert on auth.users
  for each row execute function public.handle_new_user();

-- Row Level Security: each user only sees/edits their own rows.
alter table public.profiles enable row level security;
alter table public.bookmarks enable row level security;

drop policy if exists "profiles self read"  on public.profiles;
drop policy if exists "profiles self write" on public.profiles;
create policy "profiles self read"  on public.profiles
  for select using (auth.uid() = id);
create policy "profiles self write" on public.profiles
  for update using (auth.uid() = id) with check (auth.uid() = id);

drop policy if exists "bookmarks self all" on public.bookmarks;
create policy "bookmarks self all" on public.bookmarks
  for all using (auth.uid() = user_id) with check (auth.uid() = user_id);
