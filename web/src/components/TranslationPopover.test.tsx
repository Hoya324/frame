import { screen, fireEvent } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { renderWithLang } from "@/test/lang";
import { TranslationPopover } from "@/components/TranslationPopover";

describe("TranslationPopover", () => {
  it("renders the translation by default and reveals the original in a popover", () => {
    renderWithLang(
      <TranslationPopover original="カリフォルニア…" tr={{ ko: { description: "캘리포니아…" } }} field="description" />,
      { locale: "ko" },
    );
    expect(screen.getByText("캘리포니아…")).toBeInTheDocument();   // 기본 = 번역
    expect(screen.queryByText("カリフォルニア…")).toBeNull();       // 원문은 숨김

    fireEvent.click(screen.getByRole("button", { name: /원문/ })); // 트리거 "기계번역 · 원문"
    expect(screen.getByText("カリフォルニア…")).toBeInTheDocument(); // 팝오버에 원문

    fireEvent.click(screen.getByRole("button", { name: /닫기/ }));
    expect(screen.queryByText("カリフォルニア…")).toBeNull();
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
