import { describe, expect, it } from "vitest";
import { screen } from "@testing-library/react";
import { renderWithLang } from "@/test/lang";
import { CinemaSection } from "./CinemaSection";
import { CINEMA_MODERN, CINEMA_PD } from "@/lib/cinema";

describe("CinemaSection", () => {
  it("full variant renders one detail-link card per scene", () => {
    renderWithLang(<CinemaSection variant="full" />);
    // one card per scene, each linking to its detail page (count, not an
    // O(n²) per-title scan — there are 100+ scenes)
    const cards = screen.getAllByRole("link").filter((a) =>
      a.getAttribute("href")?.startsWith("/masters/cinema/"));
    expect(cards).toHaveLength(CINEMA_MODERN.length + CINEMA_PD.length);
    // spot-check a representative few resolve to the right id
    for (const s of [CINEMA_MODERN[0], CINEMA_PD[0], CINEMA_MODERN[CINEMA_MODERN.length - 1]]) {
      const link = screen.getByText(s.title.ko).closest("a");
      expect(link, s.id).toHaveAttribute("href", `/masters/cinema/${s.id}`);
    }
  });

  it("shows modern label before the public-domain label (colour cinema leads)", () => {
    renderWithLang(<CinemaSection variant="full" />);
    const modern = screen.getByText("색을 배우는 현대 시네마");
    const pd = screen.getByText("퍼블릭 도메인 명장면");
    // modern heading appears earlier in DOM order
    expect(modern.compareDocumentPosition(pd) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
  });

  it("full variant shows each modern still with its © studio credit", () => {
    renderWithLang(<CinemaSection variant="full" />);
    for (const s of CINEMA_MODERN) {
      // some studios (e.g. Warner Bros.) recur across films → getAllByText
      expect(screen.getAllByText(`© ${s.studio}`).length, s.id).toBeGreaterThan(0);
    }
  });

  it("preview variant shows only a few cards and a 전체 보기 link to the full page", () => {
    renderWithLang(<CinemaSection variant="preview" />);
    const seeAll = screen.getByText(/전체 보기/);
    expect(seeAll.closest("a")).toHaveAttribute("href", "/masters/cinema");
    const cards = screen.getAllByRole("link").filter((a) =>
      a.getAttribute("href")?.startsWith("/masters/cinema/"));
    expect(cards.length).toBeGreaterThan(0);
    expect(cards.length).toBeLessThan(CINEMA_MODERN.length + CINEMA_PD.length);
  });
});
