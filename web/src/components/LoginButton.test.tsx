import { fireEvent, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { renderWithLang } from "@/test/lang";

const signIn = vi.fn();
const signOut = vi.fn();
let mockUser: { email: string } | null = null;
vi.mock("@/components/AuthProvider", () => ({
  useAuth: () => ({ user: mockUser, session: null, loading: false, signIn, signOut }),
}));

import { LoginButton } from "@/components/LoginButton";

describe("LoginButton", () => {
  it("shows 로그인 and calls signIn when logged out", () => {
    mockUser = null;
    renderWithLang(<LoginButton />);
    fireEvent.click(screen.getByText("로그인"));
    expect(signIn).toHaveBeenCalled();
  });
  it("shows the user email/menu when logged in", () => {
    mockUser = { email: "a@b.c" };
    renderWithLang(<LoginButton />);
    expect(screen.getByText(/a@b\.c/)).toBeInTheDocument();
  });
});
