import { fireEvent, screen, waitFor } from "@testing-library/react";
import { describe, expect, it, vi, beforeEach } from "vitest";
import { renderWithLang } from "@/test/lang";

const invoke = vi.fn();
vi.mock("@/components/AuthProvider", () => ({
  useAuth: () => ({ user: { id: "u1", email: "me@example.com" } }),
}));
vi.mock("@/lib/supabase", () => ({
  getSupabase: () => ({ functions: { invoke } }),
}));

import { FeedbackForm } from "@/components/FeedbackForm";

describe("FeedbackForm", () => {
  beforeEach(() => invoke.mockReset());

  it("prefills the reply-to email from the logged-in user", () => {
    renderWithLang(<FeedbackForm />);
    expect(screen.getByDisplayValue("me@example.com")).toBeInTheDocument();
  });

  it("blocks submit and shows an error when type is not chosen", () => {
    renderWithLang(<FeedbackForm />);
    fireEvent.change(screen.getByLabelText("내용"), { target: { value: "문제 있어요" } });
    fireEvent.click(screen.getByText("보내기"));
    expect(screen.getByText("유형을 선택해주세요.")).toBeInTheDocument();
    expect(invoke).not.toHaveBeenCalled();
  });

  it("submits a valid report and shows success", async () => {
    invoke.mockResolvedValue({ data: { ok: true }, error: null });
    renderWithLang(<FeedbackForm />);
    fireEvent.click(screen.getByText("버그"));
    fireEvent.change(screen.getByLabelText("내용"), { target: { value: "버튼이 안 눌려요" } });
    fireEvent.click(screen.getByText("보내기"));
    await waitFor(() => expect(invoke).toHaveBeenCalledWith("feedback", {
      body: { type: "bug", message: "버튼이 안 눌려요", replyTo: "me@example.com", images: [] },
    }));
    expect(await screen.findByText("제보가 전송되었습니다. 감사합니다!")).toBeInTheDocument();
  });

  it("shows a send error when the function fails", async () => {
    invoke.mockResolvedValue({ data: null, error: new Error("boom") });
    renderWithLang(<FeedbackForm />);
    fireEvent.click(screen.getByText("기타"));
    fireEvent.change(screen.getByLabelText("내용"), { target: { value: "테스트" } });
    fireEvent.click(screen.getByText("보내기"));
    expect(await screen.findByText("전송에 실패했습니다. 잠시 후 다시 시도해주세요.")).toBeInTheDocument();
  });
});
