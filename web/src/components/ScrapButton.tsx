"use client";
import { Heart } from "lucide-react";

// Visual-only until Plan 3 wires Supabase persistence.
export function ScrapButton({ active = false }: { active?: boolean }) {
  return (
    <button
      type="button"
      aria-label="스크랩"
      className="flex h-8 w-8 items-center justify-center rounded-full border border-line2 bg-black/45 text-white transition hover:bg-black/70"
    >
      <Heart size={15} fill={active ? "currentColor" : "none"} />
    </button>
  );
}
