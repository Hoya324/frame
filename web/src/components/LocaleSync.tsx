"use client";
import { useEffect, useRef } from "react";
import { useAuth } from "@/components/AuthProvider";
import { useLang } from "@/components/LanguageProvider";
import { getSupabase } from "@/lib/supabase";
import { LOCALES, type Locale } from "@/lib/i18n";

// Keeps the account's stored locale (profiles.locale) and the on-site locale in
// sync, in both directions:
//   - on login: adopt the account's saved locale (cross-device sync)
//   - on switch: write the new locale back to the account so email jobs (which
//     run server-side and can't see localStorage) send in the chosen language
// Renders nothing; mounted once inside the auth subtree.
//
// Race-safety: a user may switch language before the initial account fetch
// resolves. We never clobber that fresh choice with the stale account value,
// and we still persist it — the hydrate path checks whether the locale changed
// while the fetch was in flight (`latest` ref) and writes the user's pick.
export function LocaleSync() {
  const { user } = useAuth();
  const { locale, setLocale } = useLang();

  // Always-current locale, readable inside async callbacks (effect closures
  // capture a stale `locale`). Updated via an effect, never during render.
  const latest = useRef(locale);
  useEffect(() => {
    latest.current = locale;
  }, [locale]);

  // The user id we've already hydrated, and the last value we synced to the
  // account — gates the persist effect and avoids redundant writes.
  const hydratedFor = useRef<string | null>(null);
  const lastSynced = useRef<Locale | null>(null);

  // Hydrate once per signed-in user.
  useEffect(() => {
    if (!user) {
      hydratedFor.current = null;
      lastSynced.current = null;
      return;
    }
    if (hydratedFor.current === user.id) return;
    const localeAtStart = latest.current;
    let cancelled = false;
    getSupabase()
      .from("profiles")
      .select("locale")
      .eq("id", user.id)
      .single()
      .then(({ data, error }) => {
        if (cancelled || error) return;
        hydratedFor.current = user.id;
        const stored = data?.locale as string | undefined;
        const userPickedSinceStart = latest.current !== localeAtStart;
        if (userPickedSinceStart) {
          // The user switched while the fetch was in flight — respect their
          // choice and push it to the account instead of overwriting it.
          lastSynced.current = latest.current;
          void getSupabase().from("profiles").update({ locale: latest.current }).eq("id", user.id);
        } else if (stored && (LOCALES as string[]).includes(stored)) {
          lastSynced.current = stored as Locale;
          if (stored !== latest.current) setLocale(stored as Locale);
        } else {
          // No usable stored value — seed the account from the current choice.
          lastSynced.current = latest.current;
          void getSupabase().from("profiles").update({ locale: latest.current }).eq("id", user.id);
        }
      });
    return () => {
      cancelled = true;
    };
  }, [user, setLocale]);

  // Persist on-site switches that happen after hydration.
  useEffect(() => {
    if (!user || hydratedFor.current !== user.id) return;
    if (lastSynced.current === locale) return;
    lastSynced.current = locale;
    void getSupabase().from("profiles").update({ locale }).eq("id", user.id);
  }, [locale, user]);

  return null;
}
