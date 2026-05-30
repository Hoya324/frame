import { screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { renderWithLang } from "@/test/lang";

vi.mock("@/components/AuthProvider", () => ({
  useBookmarks: () => ({ ids: new Set<string>(), isScrapped: () => false, toggle: vi.fn() }),
}));

import { ExhibitionCard } from "@/components/ExhibitionCard";
import type { Exhibition } from "@/lib/catalog";

const E: Exhibition = {
  id: "e1", title: "을지로의 밤", titleEn: null, posterImageUrl: "https://x/p.jpg",
  description: null, medium: "photo", exhibitionType: "group", genreTags: [],
  feeType: "free", priceMin: null, priceMax: null, startDate: "2026-05-01",
  endDate: "2026-06-02", status: "ongoing", openHours: null,
  venue: { id: "v", name: "갤러리 룩스", region: "서울", district: "을지로", lat: null, lng: null },
  artists: [], sourceUrl: null, featured: false, popularityScore: null,
};

describe("ExhibitionCard", () => {
  it("renders title, venue and D-day", () => {
    renderWithLang(<ExhibitionCard exhibition={E} today={new Date("2026-05-30T00:00:00+09:00")} />);
    expect(screen.getByText("을지로의 밤")).toBeInTheDocument();
    expect(screen.getByText(/갤러리 룩스/)).toBeInTheDocument();
    expect(screen.getByText("D-3")).toBeInTheDocument();
  });
});
