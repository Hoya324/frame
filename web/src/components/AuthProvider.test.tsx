import { act, render, screen, waitFor } from "@testing-library/react";
import { describe, expect, it, vi, beforeEach } from "vitest";

// Mock the supabase client and bookmarks layer so the provider has no network.
// eslint-disable-next-line @typescript-eslint/no-explicit-any
const authState = { user: { id: "u1", email: "a@b.c" } as any };
vi.mock("@/lib/supabase", () => ({
  getSupabase: () => ({
    auth: {
      getSession: vi.fn().mockResolvedValue({ data: { session: { user: authState.user } } }),
      onAuthStateChange: vi.fn(() => ({ data: { subscription: { unsubscribe: vi.fn() } } })),
      signInWithOAuth: vi.fn(),
      signOut: vi.fn(),
    },
  }),
}));
vi.mock("@/lib/bookmarks", () => ({
  listBookmarkIds: vi.fn().mockResolvedValue(new Set<string>(["e1"])),
  addBookmark: vi.fn().mockResolvedValue(undefined),
  removeBookmark: vi.fn().mockResolvedValue(undefined),
}));

import { AuthProvider, useAuth, useBookmarks } from "@/components/AuthProvider";

function Probe() {
  const { user } = useAuth();
  const { isScrapped, toggle } = useBookmarks();
  return (
    <div>
      <span data-testid="user">{user?.email ?? "none"}</span>
      <span data-testid="e1">{isScrapped("e1") ? "yes" : "no"}</span>
      <button onClick={() => toggle("e2")}>add-e2</button>
      <span data-testid="e2">{isScrapped("e2") ? "yes" : "no"}</span>
    </div>
  );
}

describe("AuthProvider", () => {
  beforeEach(() => vi.clearAllMocks());

  it("loads session + initial bookmarks and toggles optimistically", async () => {
    render(
      <AuthProvider>
        <Probe />
      </AuthProvider>,
    );
    // session + initial bookmarks resolve on mount (bookmarks load async after user)
    expect(await screen.findByText("a@b.c")).toBeInTheDocument();
    await waitFor(() => expect(screen.getByTestId("e1")).toHaveTextContent("yes"));
    expect(screen.getByTestId("e2")).toHaveTextContent("no");

    await act(async () => {
      screen.getByText("add-e2").click();
    });
    expect(screen.getByTestId("e2")).toHaveTextContent("yes"); // optimistic add
  });
});
