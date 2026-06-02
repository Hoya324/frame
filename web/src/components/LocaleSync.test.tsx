import { act, render, waitFor } from "@testing-library/react";
import { describe, expect, it, vi, beforeEach } from "vitest";

// LocaleSync keeps profiles.locale and the on-site locale in sync. We drive the
// REAL LanguageProvider/localeStore (so the switch path is exercised end to end)
// and mock only the auth user and the supabase client.

let mockUser: { id: string } | null = { id: "u1" };
vi.mock("@/components/AuthProvider", () => ({
  useAuth: () => ({ user: mockUser }),
}));

// Supabase mock: records update() payloads, returns a configurable stored locale.
const updateCalls: Array<Record<string, unknown>> = [];
let storedLocale: string | null = "ko";
// eslint-disable-next-line @typescript-eslint/no-explicit-any
let selectError: any = null;
function makeClient() {
  return {
    from: () => ({
      select: () => ({
        eq: () => ({
          single: () =>
            Promise.resolve({
              data: storedLocale === null ? null : { locale: storedLocale },
              error: selectError,
            }),
        }),
      }),
      update: (vals: Record<string, unknown>) => ({
        eq: () => {
          updateCalls.push(vals);
          return Promise.resolve({ data: null, error: null });
        },
      }),
    }),
  };
}
vi.mock("@/lib/supabase", () => ({ getSupabase: () => makeClient() }));

import { LocaleSync } from "@/components/LocaleSync";
import { LanguageProvider } from "@/components/LanguageProvider";
import { setStoredLocale } from "@/lib/localeStore";

const flush = () => act(async () => { await Promise.resolve(); });

describe("LocaleSync", () => {
  beforeEach(() => {
    updateCalls.length = 0;
    storedLocale = "ko";
    selectError = null;
    mockUser = { id: "u1" };
    localStorage.clear();
  });

  it("persists an on-site language switch to the account", async () => {
    render(
      <LanguageProvider>
        <LocaleSync />
      </LanguageProvider>,
    );
    // let the hydrate select resolve
    await flush();

    // user switches to Japanese
    await act(async () => {
      setStoredLocale("ja");
      await Promise.resolve();
    });

    await waitFor(() =>
      expect(updateCalls).toContainEqual({ locale: "ja" }),
    );
  });

  it("persists a switch even when the account row can't be read (no row / RLS / error)", async () => {
    // Reproduces the production bug: the hydrate select fails or returns no row,
    // so the account locale is never written when the user switches language.
    storedLocale = null;
    selectError = { code: "PGRST116", message: "no rows" };

    render(
      <LanguageProvider>
        <LocaleSync />
      </LanguageProvider>,
    );
    await flush();

    await act(async () => {
      setStoredLocale("ja");
      await Promise.resolve();
    });

    await waitFor(() =>
      expect(updateCalls).toContainEqual({ locale: "ja" }),
    );
  });

  it("adopts the account's stored locale on login without re-writing it", async () => {
    storedLocale = "ja"; // account says Japanese; local default is Korean
    render(
      <LanguageProvider>
        <LocaleSync />
      </LanguageProvider>,
    );
    await flush();
    await waitFor(() => expect(document.documentElement.lang).toBe("ja"));
    // adopting the stored value must not echo back as a write
    expect(updateCalls).toEqual([]);
  });

  it("does not clobber the stored locale with the local default on login", async () => {
    // local default 'ko', account 'ja' — the login pass must never PATCH 'ko'.
    storedLocale = "ja";
    render(
      <LanguageProvider>
        <LocaleSync />
      </LanguageProvider>,
    );
    await flush();
    expect(updateCalls).not.toContainEqual({ locale: "ko" });
  });
});
