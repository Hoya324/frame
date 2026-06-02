-- supabase/migrations/0003_profiles_locale.sql
-- Persist each user's UI language so server-side email jobs can send in the
-- language the user picked in the site header (the header was previously
-- localStorage-only and invisible to the cron jobs).

alter table public.profiles
  add column if not exists locale text not null default 'ko'
  check (locale in ('ko', 'en', 'ja'));

-- Existing rows predate the column; the default backfills them to 'ko'.
