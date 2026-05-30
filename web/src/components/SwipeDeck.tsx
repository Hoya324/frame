"use client";
import { useState } from "react";
import { X, Heart, Share2 } from "lucide-react";
import { PosterImage } from "@/components/PosterImage";
import { StatusBadge } from "@/components/StatusBadge";
import { useBookmarks } from "@/components/AuthProvider";
import type { Exhibition } from "@/lib/catalog";

export function SwipeDeck({ items }: { items: Exhibition[] }) {
  const [i, setI] = useState(0);
  const { toggle, isScrapped } = useBookmarks();
  const current = items[i];
  if (!current) {
    return <div className="flex min-h-[60vh] items-center justify-center text-tx3">모두 둘러봤어요</div>;
  }
  return (
    <div className="relative mx-auto h-[70vh] max-w-md">
      <div className="absolute inset-0 overflow-hidden rounded-2xl border border-line">
        <PosterImage src={current.posterImageUrl} alt={current.title} />
        <div className="absolute inset-0 bg-gradient-to-t from-black/90 via-transparent" />
        <div className="absolute left-5 top-5"><StatusBadge e={current} /></div>
        <div className="absolute inset-x-0 bottom-24 px-6">
          <h2 className="text-3xl font-extrabold tracking-tight">{current.title}</h2>
          <div className="mt-2 text-sm text-tx2">{current.venue?.name ?? "장소 미정"}</div>
        </div>
      </div>
      <div className="absolute inset-x-0 bottom-5 flex justify-center gap-4">
        <button aria-label="넘기기" onClick={() => setI((n) => n + 1)}
          className="flex h-14 w-14 items-center justify-center rounded-full border border-line2 bg-black/50 text-white">
          <X size={20} />
        </button>
        <button aria-label={isScrapped(current.id) ? "스크랩 취소" : "스크랩"}
          onClick={() => { void toggle(current.id); setI((n) => n + 1); }}
          className="flex h-16 w-16 items-center justify-center rounded-full bg-white text-black">
          <Heart size={22} fill={isScrapped(current.id) ? "currentColor" : "none"} />
        </button>
        <button aria-label="공유"
          className="flex h-14 w-14 items-center justify-center rounded-full border border-line2 bg-black/50 text-white">
          <Share2 size={18} />
        </button>
      </div>
    </div>
  );
}
