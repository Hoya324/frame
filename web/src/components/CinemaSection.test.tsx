import { describe, expect, it } from "vitest";
import { screen } from "@testing-library/react";
import { renderWithLang } from "@/test/lang";
import { CinemaSection } from "./CinemaSection";
import { CINEMA_PD } from "@/lib/cinema";

describe("CinemaSection", () => {
  it("renders every public-domain scene as a card that links out", () => {
    renderWithLang(<CinemaSection />);
    expect(screen.getByText("영화, 한 프레임")).toBeInTheDocument();
    // each PD scene's title shows, and the card is an external link
    for (const s of CINEMA_PD) {
      const title = screen.getByText(s.title.ko);
      const link = title.closest("a");
      expect(link, s.id).not.toBeNull();
      expect(link).toHaveAttribute("href", s.url);
      expect(link).toHaveAttribute("target", "_blank");
      expect(link).toHaveAttribute("rel", expect.stringContaining("noopener"));
    }
  });

  it("hides the modern subsection while no modern still is sourced", () => {
    // CINEMA_MODERN entries currently have no `image`, so the in-copyright
    // block must not render (no broken cards, no orphan heading).
    renderWithLang(<CinemaSection />);
    expect(screen.queryByText("색을 배우는 현대 시네마")).toBeNull();
  });
});
