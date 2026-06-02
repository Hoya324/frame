import { screen, fireEvent } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { renderWithLang } from "@/test/lang";
import { TranslatableText } from "@/components/TranslatableText";

describe("TranslatableText", () => {
  it("shows the header-language translation by default and toggles to the original (ko locale)", () => {
    renderWithLang(
      <TranslatableText original="戎康友 展" tr={{ ko: { title: "에비스 전" } }} field="title" />,
      { locale: "ko" },
    );
    expect(screen.getByText("에비스 전")).toBeInTheDocument();   // 기본 = 번역
    fireEvent.click(screen.getByRole("button"));
    expect(screen.getByText("戎康友 展")).toBeInTheDocument();   // 토글 → 원문
    fireEvent.click(screen.getByRole("button"));
    expect(screen.getByText("에비스 전")).toBeInTheDocument();
  });

  it("renders plain original with no button when no translation for locale", () => {
    renderWithLang(
      <TranslatableText original="을지로의 밤" tr={{}} field="title" />,
      { locale: "ko" },
    );
    expect(screen.getByText("을지로의 밤")).toBeInTheDocument();
    expect(screen.queryByRole("button")).toBeNull();
  });
});
