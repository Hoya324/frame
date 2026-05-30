"use client";
import { Heart } from "lucide-react";
import { useBookmarks } from "@/components/AuthProvider";

export function ScrapButton({
  exhibitionId,
  size = 15,
  className = "flex h-8 w-8 items-center justify-center rounded-full border border-line2 bg-black/45 text-white transition hover:bg-black/70",
}: {
  exhibitionId: string;
  size?: number;
  className?: string;
}) {
  const { isScrapped, toggle } = useBookmarks();
  const active = isScrapped(exhibitionId);
  return (
    <button
      type="button"
      aria-label={active ? "스크랩 취소" : "스크랩"}
      aria-pressed={active}
      onClick={(e) => {
        e.preventDefault(); // don't trigger the card's parent <Link>
        e.stopPropagation();
        void toggle(exhibitionId);
      }}
      className={className}
    >
      <Heart size={size} fill={active ? "currentColor" : "none"} />
    </button>
  );
}
