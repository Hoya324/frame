import { fireEvent, screen, waitFor } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { renderWithLang } from "@/test/lang";

const signIn = vi.fn();
const invoke = vi.fn();
vi.mock("@/components/AuthProvider", () => ({
  useAuth: () => ({ user: null, signIn }),
}));
vi.mock("@/lib/supabase", () => ({
  getSupabase: () => ({ functions: { invoke } }),
}));

import { FeedbackForm } from "@/components/FeedbackForm";

describe("FeedbackForm when logged out", () => {
  it("still renders the form with a sign-in banner", () => {
    renderWithLang(<FeedbackForm />);
    expect(screen.getByText("로그인하면 제보를 보낼 수 있어요.")).toBeInTheDocument();
    expect(screen.getByText("보내기")).toBeInTheDocument();
  });

  it("triggers sign-in instead of submitting", async () => {
    renderWithLang(<FeedbackForm />);
    fireEvent.click(screen.getByText("버그"));
    fireEvent.change(screen.getByLabelText("내용"), { target: { value: "테스트" } });
    fireEvent.click(screen.getByText("보내기"));
    await waitFor(() => expect(signIn).toHaveBeenCalled());
    expect(invoke).not.toHaveBeenCalled();
  });
});
