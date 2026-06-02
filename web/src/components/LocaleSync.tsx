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
export function LocaleSync() {
  const { user } = useAuth();
  const { locale, setLocale } = useLang();
  // The locale we believe the account currently holds. null = not yet loaded,
  // which gates the persist effect so the initial hydrate doesn't echo back.
  const accountLocale = useRef<Locale | null>(null);

  // Hydrate from the account whenever the signed-in user changes.
  useEffect(() => {
    if (!user) {
      accountLocale.current = null;
      return;
    }
    let cancelled = false;
    getSupabase()
      .from("profiles")
      .select("locale")
      .eq("id", user.id)
      .single()
      .then(({ data }) => {
        if (cancelled) return;
        const stored = data?.locale as string | undefined;
        if (stored && (LOCALES as string[]).includes(stored)) {
          accountLocale.current = stored as Locale;
          if (stored !== locale) setLocale(stored as Locale);
        } else {
          // No usable stored value — seed the account from the current choice.
          accountLocale.current = locale;
          void getSupabase().from("profiles").update({ locale }).eq("id", user.id);
        }
      });
    return () => {
      cancelled = true;
    };
    // `locale` is intentionally omitted: this effect only runs on user change;
    // the persist effect below handles later locale switches.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [user, setLocale]);

  // Persist on-site switches back to the account.
  useEffect(() => {
    if (!user) return;
    if (accountLocale.current === null) return; // wait for the initial hydrate
    if (accountLocale.current === locale) return; // already in sync
    accountLocale.current = locale;
    void getSupabase().from("profiles").update({ locale }).eq("id", user.id);
  }, [locale, user]);

  return null;
}
