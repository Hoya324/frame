import { fireEvent, screen, waitFor } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { renderWithLang } from "@/test/lang";

const signIn = vi.fn();
const upsert = vi.fn();
vi.mock("@/components/AuthProvider", () => ({
  useAuth: () => ({ user: null, signIn }),
}));
vi.mock("@/lib/supabase", () => ({ getSupabase: () => ({}) }));
vi.mock("@/lib/subscriptions", () => ({
  getSubscriptions: vi.fn().mockResolvedValue({}),
  upsertSubscription: (...args: unknown[]) => upsert(...args),
}));
vi.mock("@/lib/catalogClient", () => ({
  loadCatalogSync: () => ({ exhibitions: [], venues: [] }),
}));

import { SubscriptionSettings } from "@/components/SubscriptionSettings";

describe("SubscriptionSettings when logged out", () => {
  it("renders the settings with a sign-in banner", () => {
    renderWithLang(<SubscriptionSettings />);
    expect(screen.getByText("로그인하면 알림을 설정할 수 있어요.")).toBeInTheDocument();
    expect(screen.getByText("주간 다이제스트")).toBeInTheDocument();
  });

  it("triggers sign-in instead of saving when a toggle is tapped", async () => {
    renderWithLang(<SubscriptionSettings />);
    fireEvent.click(screen.getByRole("switch", { name: "주간 다이제스트" }));
    await waitFor(() => expect(signIn).toHaveBeenCalled());
    expect(upsert).not.toHaveBeenCalled();
  });
});
