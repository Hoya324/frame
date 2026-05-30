import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

const toggle = vi.fn();
const ids = new Set<string>(["scrapped-1"]);
vi.mock("@/components/AuthProvider", () => ({
  useBookmarks: () => ({ ids, isScrapped: (id: string) => ids.has(id), toggle }),
}));

import { ScrapButton } from "@/components/ScrapButton";

describe("ScrapButton", () => {
  it("reflects scrapped state and toggles on click", () => {
    render(<ScrapButton exhibitionId="scrapped-1" />);
    const btn = screen.getByLabelText("스크랩 취소"); // already scrapped → aria reflects active
    fireEvent.click(btn);
    expect(toggle).toHaveBeenCalledWith("scrapped-1");
  });
  it("shows un-scrapped label when not saved", () => {
    render(<ScrapButton exhibitionId="other" />);
    expect(screen.getByLabelText("스크랩")).toBeInTheDocument();
  });
});
