import { fireEvent, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { renderWithLang } from "@/test/lang";

vi.mock("@/components/AuthProvider", () => ({
  useBookmarks: () => ({ ids: new Set<string>(), isScrapped: () => false, toggle: vi.fn() }),
}));

const push = vi.fn();
vi.mock("next/navigation", () => ({ useRouter: () => ({ push }) }));

import { SwipeDeck } from "@/components/SwipeDeck";
import type { Exhibition } from "@/lib/catalog";

function ex(id: string, title: string): Exhibition {
  return {
    id, title, posterImageUrl: "https://x/p.jpg", description: null,
    medium: "photo", exhibitionType: "solo", genreTags: [], feeType: "free",
    priceMin: null, priceMax: null, startDate: null, endDate: null, status: "ongoing",
    openHours: null, venue: null, artists: [], sourceUrl: null, featured: false, popularityScore: null,
    lang: null, tr: {},
  };
}

describe("SwipeDeck", () => {
  it("advances to the next card on skip", () => {
    renderWithLang(<SwipeDeck items={[ex("a", "첫번째"), ex("b", "두번째")]} />);
    const titles = ["첫번째", "두번째"];
    const first = titles.find((tl) => screen.queryByText(tl));
    expect(first).toBeTruthy();
    fireEvent.click(screen.getByLabelText("넘기기"));
    const remaining = titles.find((tl) => tl !== first)!;
    expect(screen.getByText(remaining)).toBeInTheDocument();
  });
  it("shows end state when exhausted", () => {
    renderWithLang(<SwipeDeck items={[ex("a", "유일")]} />);
    fireEvent.click(screen.getByLabelText("넘기기"));
    expect(screen.getByText(/모두 둘러봤어요/)).toBeInTheDocument();
  });
  it("opens the detail page on a tap with no drag", () => {
    push.mockClear();
    renderWithLang(<SwipeDeck items={[ex("a", "유일")]} />);
    const card = screen.getByTestId("swipe-card");
    fireEvent.pointerDown(card, { clientX: 100, clientY: 100 });
    fireEvent.pointerUp(card, { clientX: 100, clientY: 100 });
    expect(push).toHaveBeenCalledWith("/exhibitions/a");
  });
});
