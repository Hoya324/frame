import { describe, expect, it } from "vitest";
import { screen } from "@testing-library/react";
import { renderWithLang } from "@/test/lang";
import { CinemaSection } from "./CinemaSection";

describe("CinemaSection (hub preview)", () => {
  it("shows the title and a 전체 보기 link to the full cinema page", () => {
    renderWithLang(<CinemaSection />);
    expect(screen.getByText("영화, 한 프레임")).toBeInTheDocument();
    const seeAll = screen.getByText(/전체 보기/);
    expect(seeAll.closest("a")).toHaveAttribute("href", "/masters/cinema");
  });

  it("renders only a small preview, each card linking to a detail page", () => {
    renderWithLang(<CinemaSection />);
    const cards = screen.getAllByRole("link").filter((a) =>
      a.getAttribute("href")?.startsWith("/masters/cinema/"));
    expect(cards.length).toBeGreaterThan(0);
    expect(cards.length).toBeLessThanOrEqual(6); // preview, not the whole catalogue
  });
});
