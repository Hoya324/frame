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
vi.mock("next/navigation", () => ({ useRouter: () => ({ push: vi.fn() }) }));
vi.mock("next/dynamic", () => ({
  default: () => () => null,
}));

import MapPage from "@/app/map/page";

describe("Map page — default filter state", () => {
  it("activates 진행중 and 예정 chips on initial render", () => {
    renderWithLang(<MapPage />);
    expect(screen.getByText("진행중")).toHaveClass("bg-white");
    expect(screen.getByText("예정")).toHaveClass("bg-white");
  });

  it("does not activate 종료 chip on initial render", () => {
    renderWithLang(<MapPage />);
    expect(screen.getByText("종료")).not.toHaveClass("bg-white");
  });
});
