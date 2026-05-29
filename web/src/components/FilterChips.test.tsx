import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { FilterChips } from "@/components/FilterChips";

describe("FilterChips", () => {
  it("toggles a chip and reports the change", () => {
    const onToggle = vi.fn();
    render(<FilterChips options={[{ value: "ongoing", label: "진행중" }]} active={[]} onToggle={onToggle} />);
    fireEvent.click(screen.getByText("진행중"));
    expect(onToggle).toHaveBeenCalledWith("ongoing");
  });
  it("marks active chips", () => {
    render(<FilterChips options={[{ value: "free", label: "무료" }]} active={["free"]} onToggle={() => {}} />);
    expect(screen.getByText("무료")).toHaveClass("bg-white");
  });
});
