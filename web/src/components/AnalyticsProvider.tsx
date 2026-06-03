"use client";
import { useEffect, useRef } from "react";
import { useAuth } from "@/components/AuthProvider";
import { useLang } from "@/components/LanguageProvider";
import {
  initAnalytics,
  identifyUser,
  resetUser,
  setUserProperty,
} from "@/lib/analytics";

/**
 * Side-effect-only component (renders nothing). Boots Amplitude once, keeps the
 * identity in sync with the Supabase session, and stamps the preferred locale.
 * Mounted inside both LanguageProvider and AuthProvider so it can read each.
 */
export function AnalyticsProvider() {
  const { user } = useAuth();
  const { locale } = useLang();
  const identified = useRef(false);

  useEffect(() => {
    initAnalytics();
  }, []);

  useEffect(() => {
    if (user) {
      identifyUser(user.id, { email: user.email, locale });
      identified.current = true;
    } else if (identified.current) {
      // Only reset on a real sign-out, not on the initial anonymous render.
      resetUser();
      identified.current = false;
    }
    // locale is stamped via its own effect; depend on user fields only here.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [user]);

  useEffect(() => {
    setUserProperty("locale", locale);
  }, [locale]);

  return null;
}
