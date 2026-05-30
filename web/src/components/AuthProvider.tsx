"use client";
import { createContext, useCallback, useContext, useEffect, useMemo, useState } from "react";
import type { Session, User } from "@supabase/supabase-js";
import { getSupabase } from "@/lib/supabase";
import { addBookmark, listBookmarkIds, removeBookmark } from "@/lib/bookmarks";

interface AuthCtx {
  user: User | null;
  session: Session | null;
  loading: boolean;
  signIn: () => Promise<void>;
  signOut: () => Promise<void>;
}
interface BookmarksCtx {
  ids: Set<string>;
  isScrapped: (id: string) => boolean;
  toggle: (id: string) => Promise<void>;
}

const AuthContext = createContext<AuthCtx | null>(null);
const BookmarksContext = createContext<BookmarksCtx | null>(null);

// OAuth must return to the app's own path. With basePath "/frame" the bare
// origin is not in Supabase's redirect allowlist, so include the basePath.
function redirectTarget(): string | undefined {
  if (typeof window === "undefined") return undefined;
  const basePath = process.env.NEXT_PUBLIC_BASE_PATH ?? "";
  return `${window.location.origin}${basePath}/`;
}

export function AuthProvider({ children }: { children: React.ReactNode }) {
  // Stable for the component's lifetime: getSupabase() is a singleton, but
  // memoizing keeps the reference identity fixed so the effects below don't
  // re-fire (and re-fetch) on every render.
  const supabase = useMemo(() => getSupabase(), []);
  const [session, setSession] = useState<Session | null>(null);
  const [loading, setLoading] = useState(true);
  const [ids, setIds] = useState<Set<string>>(new Set());

  const user = session?.user ?? null;

  // Load session + subscribe to changes.
  useEffect(() => {
    let active = true;
    supabase.auth.getSession().then(({ data }) => {
      if (active) {
        setSession(data.session ?? null);
        setLoading(false);
      }
    });
    const { data: sub } = supabase.auth.onAuthStateChange((_e, s) => setSession(s));
    return () => {
      active = false;
      sub.subscription.unsubscribe();
    };
  }, [supabase]);

  // Load bookmarks whenever the user changes; an empty set when signed out.
  useEffect(() => {
    let active = true;
    const load = async () =>
      user ? await listBookmarkIds(supabase, user.id) : new Set<string>();
    load()
      .then((s) => {
        if (active) setIds(s);
      })
      .catch(() => {});
    return () => {
      active = false;
    };
  }, [supabase, user]);

  const signIn = useCallback(async () => {
    await supabase.auth.signInWithOAuth({
      provider: "google",
      options: { redirectTo: redirectTarget() },
    });
  }, [supabase]);

  const signOut = useCallback(async () => {
    await supabase.auth.signOut();
  }, [supabase]);

  const toggle = useCallback(
    async (id: string) => {
      if (!user) {
        await signIn();
        return;
      }
      const has = ids.has(id);
      // optimistic
      setIds((prev) => {
        const next = new Set(prev);
        if (has) next.delete(id);
        else next.add(id);
        return next;
      });
      try {
        if (has) await removeBookmark(supabase, user.id, id);
        else await addBookmark(supabase, user.id, id);
      } catch {
        // rollback on failure
        setIds((prev) => {
          const next = new Set(prev);
          if (has) next.add(id);
          else next.delete(id);
          return next;
        });
      }
    },
    [supabase, user, ids, signIn],
  );

  const authValue = useMemo<AuthCtx>(
    () => ({ user, session, loading, signIn, signOut }),
    [user, session, loading, signIn, signOut],
  );
  const bmValue = useMemo<BookmarksCtx>(
    () => ({ ids, isScrapped: (id) => ids.has(id), toggle }),
    [ids, toggle],
  );

  return (
    <AuthContext.Provider value={authValue}>
      <BookmarksContext.Provider value={bmValue}>{children}</BookmarksContext.Provider>
    </AuthContext.Provider>
  );
}

export function useAuth(): AuthCtx {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used within AuthProvider");
  return ctx;
}
export function useBookmarks(): BookmarksCtx {
  const ctx = useContext(BookmarksContext);
  if (!ctx) throw new Error("useBookmarks must be used within AuthProvider");
  return ctx;
}
