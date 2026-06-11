import { screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { renderWithLang } from "@/test/lang";

vi.mock("@/lib/catalogClient", () => ({
  loadCatalogSync: () => ({ exhibitions: [], venues: [] }),
}));
vi.mock("@/components/AuthProvider", () => ({
  useAuth: () => ({ user: { id: "u1" }, loading: false, signIn: vi.fn() }),
  useBookmarks: () => ({ ids: new Set(), isScrapped: () => false, toggle: vi.fn() }),
}));

import ScrapPage from "@/app/scrap/page";

describe("Scrap page — default filter state", () => {
  it("activates 진행중 and 예정 chips on initial render", () => {
    renderWithLang(<ScrapPage />);
    expect(screen.getByText("진행중")).toHaveClass("bg-white");
    expect(screen.getByText("예정")).toHaveClass("bg-white");
  });

  it("does not activate 종료 chip on initial render", () => {
    renderWithLang(<ScrapPage />);
    expect(screen.getByText("종료")).not.toHaveClass("bg-white");
  });
});
