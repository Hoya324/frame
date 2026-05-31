"use client";
import { useEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import { X, Heart, Share2 } from "lucide-react";
import { PosterImage } from "@/components/PosterImage";
import { StatusBadge } from "@/components/StatusBadge";
import { useBookmarks } from "@/components/AuthProvider";
import { useLang } from "@/components/LanguageProvider";
import { localized, type Exhibition } from "@/lib/catalog";

// Fisher–Yates shuffle so the deck order is fresh on every mount.
function shuffle<T>(input: T[]): T[] {
  const a = [...input];
  for (let i = a.length - 1; i > 0; i--) {
    const j = Math.floor(Math.random() * (i + 1));
    [a[i], a[j]] = [a[j], a[i]];
  }
  return a;
}

const SWIPE_THRESHOLD = 90;
// Below this much pointer travel, a release counts as a tap (not a drag).
const TAP_THRESHOLD = 8;

export function SwipeDeck({ items }: { items: Exhibition[] }) {
  // Shuffle once on mount. `items` is a fresh array on every parent render
  // (a bookmark toggle re-renders the tree), so deriving from it would reshuffle.
  const [deck] = useState(() => shuffle(items));
  const [i, setI] = useState(0);
  const [drag, setDrag] = useState({ x: 0, y: 0 });
  // The card currently flying off-screen, rendered as a throwaway ghost overlay.
  const [leaving, setLeaving] = useState<{ card: Exhibition; dir: "left" | "right" } | null>(null);
  const dragging = useRef(false);
  const start = useRef({ x: 0, y: 0 });
  // Fallback timer to drop the ghost even when animationend never fires
  // (reduced-motion users, or environments that disable CSS animations).
  const leaveTimer = useRef<ReturnType<typeof setTimeout> | null>(null);
  useEffect(() => () => { if (leaveTimer.current) clearTimeout(leaveTimer.current); }, []);
  const { toggle, isScrapped } = useBookmarks();
  const { t, locale } = useLang();
  const router = useRouter();
  const [copied, setCopied] = useState(false);
  const copiedTimer = useRef<ReturnType<typeof setTimeout> | null>(null);
  useEffect(() => () => { if (copiedTimer.current) clearTimeout(copiedTimer.current); }, []);

  const current = deck[i];

  if (!current) {
    return (
      <div className="flex min-h-[60vh] animate-[fadeIn_.4s_ease] items-center justify-center text-tx3">
        {t("swipe.done")}
      </div>
    );
  }

  // Advance synchronously, then let the ghost animate away on its own. Keeping
  // the index update in the click/release handler (not a delayed timer) avoids
  // stale-closure / double-fiber races.
  const fling = (dir: "left" | "right") => {
    if (dir === "right") void toggle(current.id);
    setLeaving({ card: current, dir });
    setI((n) => n + 1);
    if (leaveTimer.current) clearTimeout(leaveTimer.current);
    leaveTimer.current = setTimeout(() => setLeaving(null), 360);
  };

  const onPointerDown = (e: React.PointerEvent) => {
    dragging.current = true;
    start.current = { x: e.clientX, y: e.clientY };
    (e.target as HTMLElement).setPointerCapture?.(e.pointerId);
  };
  const onPointerMove = (e: React.PointerEvent) => {
    if (!dragging.current) return;
    setDrag({ x: e.clientX - start.current.x, y: e.clientY - start.current.y });
  };
  const onPointerUp = () => {
    if (!dragging.current) return;
    dragging.current = false;
    const dx = drag.x;
    const dy = drag.y;
    setDrag({ x: 0, y: 0 });
    if (dx > SWIPE_THRESHOLD) fling("right");
    else if (dx < -SWIPE_THRESHOLD) fling("left");
    else if (Math.abs(dx) < TAP_THRESHOLD && Math.abs(dy) < TAP_THRESHOLD)
      router.push(`/exhibitions/${current.id}`);
  };

  const share = async () => {
    const basePath = process.env.NEXT_PUBLIC_BASE_PATH ?? "";
    const url = `${window.location.origin}${basePath}/exhibitions/${current.id}`;
    const title = localized(current.title, current.tr, locale, "title") ?? current.title;
    if (typeof navigator !== "undefined" && navigator.share) {
      try {
        await navigator.share({ title, url });
      } catch {
        // user dismissed the share sheet — nothing to do
      }
      return;
    }
    try {
      await navigator.clipboard.writeText(url);
      setCopied(true);
      if (copiedTimer.current) clearTimeout(copiedTimer.current);
      copiedTimer.current = setTimeout(() => setCopied(false), 1600);
    } catch {
      // clipboard unavailable (e.g. insecure context) — silently ignore
    }
  };

  const rot = drag.x / 18;
  const transform = `translate(${drag.x}px, ${drag.y * 0.4}px) rotate(${rot}deg)`;
  const transition = dragging.current ? "none" : "transform .28s cubic-bezier(.22,.61,.36,1)";
  const likeOpacity = Math.max(0, Math.min(1, drag.x / SWIPE_THRESHOLD));
  const skipOpacity = Math.max(0, Math.min(1, -drag.x / SWIPE_THRESHOLD));

  return (
    <div className="relative mx-auto h-full max-w-md select-none" data-i={i}>
      {/* ghost: the card that was just flung, animating off-screen then removed */}
      {leaving && (
        <div
          key={`leaving-${leaving.card.id}`}
          data-testid="swipe-ghost"
          onAnimationEnd={() => setLeaving(null)}
          style={{ animation: `fling${leaving.dir === "right" ? "Right" : "Left"} .34s cubic-bezier(.22,.61,.36,1) forwards` }}
          className="pointer-events-none absolute inset-0 z-20 overflow-hidden rounded-2xl border border-line"
        >
          <PosterImage src={leaving.card.posterImageUrl} alt={leaving.card.title} />
          <div className="absolute inset-0 bg-gradient-to-t from-black/90 via-transparent" />
        </div>
      )}

      {/* top card */}
      <div
        key={current.id}
        data-testid="swipe-card"
        onPointerDown={onPointerDown}
        onPointerMove={onPointerMove}
        onPointerUp={onPointerUp}
        onPointerCancel={onPointerUp}
        style={{ transform, transition, touchAction: "none" }}
        className="absolute inset-0 animate-[cardIn_.3s_cubic-bezier(.22,.61,.36,1)] cursor-grab touch-none overflow-hidden rounded-2xl border border-line active:cursor-grabbing"
      >
        <PosterImage src={current.posterImageUrl} alt={current.title} />
        <div className="absolute inset-0 bg-gradient-to-t from-black/90 via-transparent" />
        <div className="absolute left-5 top-5"><StatusBadge e={current} /></div>

        {/* drag intent overlays */}
        <div
          className="pointer-events-none absolute left-6 top-6 rotate-[-12deg] rounded-lg border-2 border-emerald-400 px-3 py-1 text-lg font-extrabold uppercase tracking-wider text-emerald-400"
          style={{ opacity: likeOpacity }}
        >
          {t("swipe.like")}
        </div>
        <div
          className="pointer-events-none absolute right-6 top-6 rotate-[12deg] rounded-lg border-2 border-rose-400 px-3 py-1 text-lg font-extrabold uppercase tracking-wider text-rose-400"
          style={{ opacity: skipOpacity }}
        >
          {t("swipe.skip")}
        </div>

        <div className="absolute inset-x-0 bottom-24 px-6">
          <h2 className="text-3xl font-extrabold tracking-tight">{current.title}</h2>
          <div className="mt-2 text-sm text-tx2">{current.venue?.name ?? t("common.venueTbd")}</div>
        </div>
      </div>

      <div className="absolute inset-x-0 bottom-5 z-30 flex justify-center gap-4">
        <button aria-label={t("swipe.skip")} onClick={() => fling("left")}
          className="flex h-14 w-14 items-center justify-center rounded-full border border-line2 bg-black/50 text-white transition active:scale-90 hover:border-rose-400 hover:text-rose-400">
          <X size={20} />
        </button>
        <button aria-label={isScrapped(current.id) ? t("scrap.remove") : t("scrap.add")}
          onClick={() => fling("right")}
          className="flex h-16 w-16 items-center justify-center rounded-full bg-white text-black transition active:scale-90 hover:scale-105">
          <Heart size={22} fill={isScrapped(current.id) ? "currentColor" : "none"} />
        </button>
        <button aria-label={t("common.share")} onClick={share}
          className="flex h-14 w-14 items-center justify-center rounded-full border border-line2 bg-black/50 text-white transition active:scale-90 hover:border-white">
          <Share2 size={18} />
        </button>
      </div>

      {copied && (
        <div className="pointer-events-none absolute inset-x-0 bottom-24 z-40 flex justify-center">
          <div className="animate-[fadeIn_.2s_ease] rounded-full bg-white px-4 py-2 text-sm font-medium text-black shadow-lg">
            {t("common.linkCopied")}
          </div>
        </div>
      )}
    </div>
  );
}
