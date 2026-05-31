import { screen, fireEvent } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { renderWithLang } from "@/test/lang";
import { TranslationPopover } from "@/components/TranslationPopover";

describe("TranslationPopover", () => {
  it("renders original, opens popover with translation, and closes it", () => {
    renderWithLang(
      <TranslationPopover original="カリフォルニア…" tr={{ ko: { description: "캘리포니아…" } }} field="description" />,
      { locale: "ko" },
    );
    expect(screen.getByText("カリフォルニア…")).toBeInTheDocument();
    expect(screen.queryByText("캘리포니아…")).toBeNull();

    fireEvent.click(screen.getByRole("button", { name: /번역/ }));
    expect(screen.getByText("캘리포니아…")).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: /닫기/ }));
    expect(screen.queryByText("캘리포니아…")).toBeNull();
  });

  it("renders plain text with no trigger when no translation", () => {
    renderWithLang(
      <TranslationPopover original="국문 소개" tr={{}} field="description" />,
      { locale: "ko" },
    );
    expect(screen.getByText("국문 소개")).toBeInTheDocument();
    expect(screen.queryByRole("button")).toBeNull();
  });
});
