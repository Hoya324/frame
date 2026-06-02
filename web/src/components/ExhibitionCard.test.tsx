import { screen, fireEvent } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { renderWithLang } from "@/test/lang";

vi.mock("@/components/AuthProvider", () => ({
  useBookmarks: () => ({ ids: new Set<string>(), isScrapped: () => false, toggle: vi.fn() }),
}));

import { ExhibitionCard } from "@/components/ExhibitionCard";
import type { Exhibition } from "@/lib/catalog";

const E: Exhibition = {
  id: "e1", source: "artmap", title: "을지로의 밤", posterImageUrl: "https://x/p.jpg",
  description: null, medium: "photo", exhibitionType: "group", genreTags: [],
  feeType: "free", priceMin: null, priceMax: null, startDate: "2026-05-01",
  endDate: "2026-06-02", status: "ongoing", openHours: null,
  venue: { id: "v", name: "갤러리 룩스", region: "서울", district: "을지로", lat: null, lng: null, lang: null, tr: {} },
  artists: [], sourceUrl: null, featured: false, popularityScore: null,
  lang: null, tr: {},
};

describe("ExhibitionCard", () => {
  it("renders title, venue and D-day", () => {
    renderWithLang(<ExhibitionCard exhibition={E} today={new Date("2026-05-30T00:00:00+09:00")} />);
    expect(screen.getByText("을지로의 밤")).toBeInTheDocument();
    expect(screen.getByText(/갤러리 룩스/)).toBeInTheDocument();
    expect(screen.getByText("D-3")).toBeInTheDocument();
    expect(screen.getByText(/ARTMAP/)).toBeInTheDocument();
  });

  it("offers translation toggle when tr exists for current locale", () => {
    const JP: Exhibition = {
      ...E, id: "e2", title: "戎康友 展", lang: "ja",
      tr: { ko: { title: "에비스 전" } },
      venue: { ...E.venue!, name: "BOOK AND SONS", lang: "en", tr: { ko: { name: "북앤선즈" } } },
    };
    renderWithLang(<ExhibitionCard exhibition={JP} today={new Date("2026-05-30T00:00:00+09:00")} />, { locale: "ko" });
    expect(screen.getByText("에비스 전")).toBeInTheDocument();            // 기본 = 헤더 언어 번역
    fireEvent.click(screen.getAllByRole("button", { name: "원문" })[0]);  // 첫 원문 칩(제목) 토글
    expect(screen.getByText("戎康友 展")).toBeInTheDocument();
  });
});
