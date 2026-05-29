import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { SwipeDeck } from "@/components/SwipeDeck";
import type { Exhibition } from "@/lib/catalog";

function ex(id: string, title: string): Exhibition {
  return {
    id, title, titleEn: null, posterImageUrl: "https://x/p.jpg", description: null,
    medium: "photo", exhibitionType: "solo", genreTags: [], feeType: "free",
    priceMin: null, priceMax: null, startDate: null, endDate: null, status: "ongoing",
    openHours: null, venue: null, artists: [], sourceUrl: null, featured: false, popularityScore: null,
  };
}

describe("SwipeDeck", () => {
  it("advances to the next card on skip", () => {
    render(<SwipeDeck items={[ex("a", "첫번째"), ex("b", "두번째")]} />);
    expect(screen.getByText("첫번째")).toBeInTheDocument();
    fireEvent.click(screen.getByLabelText("넘기기"));
    expect(screen.getByText("두번째")).toBeInTheDocument();
  });
  it("shows end state when exhausted", () => {
    render(<SwipeDeck items={[ex("a", "유일")]} />);
    fireEvent.click(screen.getByLabelText("넘기기"));
    expect(screen.getByText(/모두 둘러봤어요/)).toBeInTheDocument();
  });
});
