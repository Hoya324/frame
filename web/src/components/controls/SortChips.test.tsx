import { screen, fireEvent } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { renderWithLang } from "@/test/lang";
import { SortChips } from "@/components/controls/SortChips";

describe("SortChips", () => {
  it("renders the given options and marks the active one", () => {
    renderWithLang(<SortChips value="recommended" options={["recommended", "closing", "recent"]} onChange={vi.fn()} />);
    expect(screen.getByRole("button", { name: "추천순" })).toHaveAttribute("aria-pressed", "true");
    expect(screen.getByRole("button", { name: "마감임박" })).toHaveAttribute("aria-pressed", "false");
  });
  it("calls onChange with the picked key", () => {
    const onChange = vi.fn();
    renderWithLang(<SortChips value="recommended" options={["recommended", "recent"]} onChange={onChange} />);
    fireEvent.click(screen.getByRole("button", { name: "최신순" }));
    expect(onChange).toHaveBeenCalledWith("recent");
  });
});
