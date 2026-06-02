import { screen, fireEvent, waitFor } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { renderWithLang } from "@/test/lang";

vi.mock("@/components/AuthProvider", () => ({
  useBookmarks: () => ({ ids: new Set<string>(), isScrapped: () => false, toggle: vi.fn() }),
}));

import { VenueSheet } from "@/components/VenueSheet";
import type { Exhibition, VenueEmbed } from "@/lib/catalog";

const VENUE: VenueEmbed = {
  id: "v1", name: "캐논갤러리", region: "부산", district: "해운대구",
  lat: 35.16, lng: 129.16, lang: null, tr: {},
};

function ex(id: string, p: Partial<Exhibition>): Exhibition {
  return {
    id, source: null, title: p.title ?? id, posterImageUrl: null,
    description: null, medium: null, exhibitionType: null, genreTags: [],
    feeType: null, priceMin: null, priceMax: null,
    startDate: p.startDate ?? null, endDate: p.endDate ?? null,
    status: p.status ?? "unknown", openHours: null, venue: VENUE,
    artists: [], sourceUrl: null, featured: false, popularityScore: null,
    lang: null, tr: {},
  };
}

const ITEMS: Exhibition[] = [
  ex("e-past", { title: "지난전시", status: "past", startDate: "2026-01-01", endDate: "2026-02-01" }),
  ex("e-soon", { title: "곧마감", status: "ongoing", startDate: "2026-05-01", endDate: "2026-06-05" }),
  ex("e-later", { title: "여유전시", status: "ongoing", startDate: "2026-05-20", endDate: "2026-07-01" }),
];

describe("VenueSheet", () => {
  // 카드 제목의 DOM 등장 순서를 반환 (ExhibitionCard 제목은 heading이 아니라 div이므로
  // role 대신 텍스트 노드의 문서 위치로 순서를 판정한다).
  function cardTitlesInOrder(): string[] {
    const titles = ["곧마감", "여유전시", "지난전시"];
    return titles
      .map((tt) => ({ tt, node: screen.getByText(tt) }))
      .sort((a, b) =>
        a.node.compareDocumentPosition(b.node) & Node.DOCUMENT_POSITION_FOLLOWING ? -1 : 1,
      )
      .map((p) => p.tt);
  }

  it("renders venue name, location and status summary", () => {
    renderWithLang(<VenueSheet venue={VENUE} exhibitions={ITEMS} onClose={vi.fn()} />);
    expect(screen.getByRole("heading", { name: /캐논갤러리/ })).toBeInTheDocument();
    expect(screen.getByText(/부산 · 해운대구/)).toBeInTheDocument();
    const summary = screen.getByTestId("venue-summary");
    expect(summary.textContent).toContain("3");
    expect(summary.textContent).toContain("진행중 2");
  });

  it("renders one card per exhibition", () => {
    renderWithLang(<VenueSheet venue={VENUE} exhibitions={ITEMS} onClose={vi.fn()} />);
    expect(screen.getByText("곧마감")).toBeInTheDocument();
    expect(screen.getByText("여유전시")).toBeInTheDocument();
    expect(screen.getByText("지난전시")).toBeInTheDocument();
  });

  it("default ongoing sort lists ongoing exhibitions before past", () => {
    renderWithLang(<VenueSheet venue={VENUE} exhibitions={ITEMS} onClose={vi.fn()} />);
    expect(cardTitlesInOrder()[2]).toBe("지난전시");
  });

  it("switching to '마감임박' puts the soonest-closing ongoing first", () => {
    renderWithLang(<VenueSheet venue={VENUE} exhibitions={ITEMS} onClose={vi.fn()} />);
    fireEvent.click(screen.getByRole("button", { name: "마감임박" }));
    expect(cardTitlesInOrder()[0]).toBe("곧마감");
  });

  it("calls onClose when the backdrop is clicked (after the exit animation)", async () => {
    const onClose = vi.fn();
    renderWithLang(<VenueSheet venue={VENUE} exhibitions={ITEMS} onClose={onClose} />);
    fireEvent.click(screen.getAllByRole("button", { name: "닫기" })[0]);
    await waitFor(() => expect(onClose).toHaveBeenCalled());
  });
});
