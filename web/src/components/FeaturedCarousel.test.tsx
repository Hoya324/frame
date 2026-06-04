import { describe, expect, it, vi, beforeEach, afterEach } from "vitest";
import { screen, act } from "@testing-library/react";
import { renderWithLang } from "@/test/lang";
import { FeaturedCarousel } from "./FeaturedCarousel";
import type { Master } from "@/lib/masters";

function master(id: string): Master {
  return {
    id, name: `Name-${id}`, region: "foreign", nationality: "FR", birthYear: 1857,
    deathYear: 1927, tagline: "tag", bio: "bio", portraitUrl: `https://x/${id}.jpg`,
    lang: "ko", tr: {},
    works: [{ id: `${id}-1`, title: "w", year: "1900", medium: "m",
      imageUrl: `https://x/${id}-1.jpg`, thumbUrl: `https://x/${id}-1t.jpg`,
      source: "the_met", sourceUrl: "https://x/1", credit: "c", commentary: "c",
      lang: "ko", tr: {} }],
  };
}

describe("FeaturedCarousel", () => {
  beforeEach(() => vi.useFakeTimers());
  afterEach(() => vi.useRealTimers());

  it("renders a master slide with the master name", () => {
    renderWithLang(
      <FeaturedCarousel exhibitions={[]} masters={[master("a")]} rng={() => 0} />,
    );
    expect(screen.getByText("Name-a")).toBeInTheDocument();
  });

  it("advances to the next slide after 1.4s", () => {
    renderWithLang(
      <FeaturedCarousel exhibitions={[]} masters={[master("a"), master("b")]}
        rng={() => 0} masterCount={2} />,
    );
    const firstActive = screen.getByTestId("carousel-active").textContent;
    act(() => { vi.advanceTimersByTime(1400); });
    const nextActive = screen.getByTestId("carousel-active").textContent;
    expect(nextActive).not.toBe(firstActive);
  });
});
