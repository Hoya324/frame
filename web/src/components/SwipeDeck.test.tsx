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
    id, source: null, title, posterImageUrl: "https://x/p.jpg", description: null,
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
  it("shows the locale translation with a pill that toggles to the original", () => {
    push.mockClear();
    // Japanese original with a Korean translation; default header locale is ko.
    const item: Exhibition = { ...ex("a", "頂上"), tr: { ko: { title: "이름" } } };
    renderWithLang(<SwipeDeck items={[item]} />);
    const heading = () => screen.getByRole("heading", { level: 2 });
    expect(heading()).toHaveTextContent("이름");

    const pill = screen.getByRole("button", { name: "원문" });
    // A tap on the pill must not start a drag or open the detail page.
    fireEvent.pointerDown(pill, { clientX: 10, clientY: 10 });
    fireEvent.pointerUp(pill, { clientX: 10, clientY: 10 });
    fireEvent.click(pill);
    expect(heading()).toHaveTextContent("頂上");
    expect(screen.getByRole("button", { name: "번역" })).toBeInTheDocument();
    expect(push).not.toHaveBeenCalled();
  });
  it("shows no translation pill when the original matches the locale", () => {
    renderWithLang(<SwipeDeck items={[ex("a", "한글 제목")]} />);
    expect(screen.queryByRole("button", { name: "원문" })).toBeNull();
    expect(screen.getByRole("heading", { level: 2 })).toHaveTextContent("한글 제목");
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
