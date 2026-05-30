import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

vi.mock("@/components/AuthProvider", () => ({
  useAuth: () => ({ user: null, session: null, loading: false, signIn: vi.fn(), signOut: vi.fn() }),
}));

import { Nav } from "@/components/Nav";

describe("Nav", () => {
  it("renders the primary destinations", () => {
    render(<Nav />);
    for (const label of ["둘러보기", "검색", "지도", "스크랩"]) {
      expect(screen.getAllByText(label).length).toBeGreaterThan(0);
    }
  });
});
