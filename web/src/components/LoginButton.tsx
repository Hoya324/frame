"use client";
import { LogOut } from "lucide-react";
import { useAuth } from "@/components/AuthProvider";

export function LoginButton() {
  const { user, loading, signIn, signOut } = useAuth();
  if (loading) return <div className="h-9 w-20 animate-pulse rounded-md bg-panel2" />;
  if (!user) {
    return (
      <button
        onClick={() => void signIn()}
        className="rounded-md bg-white px-4 py-2 text-sm font-semibold text-black transition hover:bg-tx2"
      >
        로그인
      </button>
    );
  }
  return (
    <div className="flex items-center gap-2">
      <span className="max-w-[160px] truncate text-sm text-tx2">{user.email}</span>
      <button
        onClick={() => void signOut()}
        aria-label="로그아웃"
        className="flex h-8 w-8 items-center justify-center rounded-md border border-line text-tx2 hover:text-tx"
      >
        <LogOut size={15} />
      </button>
    </div>
  );
}
