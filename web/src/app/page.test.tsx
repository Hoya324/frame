import { screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { renderWithLang } from "@/test/lang";

vi.mock("@/lib/catalogClient", () => ({
  loadCatalogSync: () => ({ exhibitions: [], venues: [] }),
}));
vi.mock("@/components/AuthProvider", () => ({
  useAuth: () => ({ user: null }),
  useBookmarks: () => ({ ids: new Set(), isScrapped: () => false, toggle: vi.fn() }),
}));
vi.mock("@/components/OnboardingProvider", () => ({
  useOnboarding: () => ({ isSwipeStep: false }),
}));
vi.mock("../../public/data/masters.json", () => ({ default: { masters: [], works: [] } }));

import Home from "@/app/page";

describe("Home page — default filter state", () => {
  it("activates 진행중 and 예정 chips on initial render", () => {
    renderWithLang(<Home />);
    const ongoing = screen.getByText("진행중");
    const upcoming = screen.getByText("예정");
    // Active chips have bg-white class (same check as FilterChips.test.tsx)
    expect(ongoing).toHaveClass("bg-white");
    expect(upcoming).toHaveClass("bg-white");
  });

  it("does not activate 종료 chip on initial render", () => {
    renderWithLang(<Home />);
    expect(screen.getByText("종료")).not.toHaveClass("bg-white");
  });
});
