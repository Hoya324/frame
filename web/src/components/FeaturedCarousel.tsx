"use client";
import { useEffect, useMemo, useRef, useState } from "react";
import Link from "next/link";
import { PosterImage } from "@/components/PosterImage";
import { useLang } from "@/components/LanguageProvider";
import { buildCarouselSlides, type CarouselSlide } from "@/lib/carousel";
import type { Master } from "@/lib/masters";
import type { Exhibition } from "@/lib/catalog";

const ADVANCE_MS = 1400;

function prefersReducedMotion(): boolean {
  return typeof window !== "undefined"
    && window.matchMedia?.("(prefers-reduced-motion: reduce)").matches === true;
}

export function FeaturedCarousel({
  exhibitions,
  masters,
  masterCount = 6,
  rng,
}: {
  exhibitions: Exhibition[];
  masters: Master[];
  masterCount?: number;
  rng?: () => number;
}) {
  const { t } = useLang();
  // Build the slide list once per mount so it stays stable while advancing, but
  // is reshuffled (random masters) on each fresh load.
  const slides = useMemo<CarouselSlide[]>(
    () => buildCarouselSlides(exhibitions, masters, { masterCount, rng }),
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [],
  );
  const [index, setIndex] = useState(0);
  const [paused, setPaused] = useState(false);
  const reduced = useRef(false);
  useEffect(() => { reduced.current = prefersReducedMotion(); }, []);

  useEffect(() => {
    if (slides.length <= 1 || paused || reduced.current) return;
    const id = setInterval(() => setIndex((i) => (i + 1) % slides.length), ADVANCE_MS);
    return () => clearInterval(id);
  }, [slides.length, paused]);

  if (slides.length === 0) return null;
  const active = slides[index % slides.length];

  return (
    <section
      className="relative mb-9 min-h-[320px] overflow-hidden rounded border border-line"
      onMouseEnter={() => setPaused(true)}
      onMouseLeave={() => setPaused(false)}
      onFocusCapture={() => setPaused(true)}
      onBlurCapture={() => setPaused(false)}
      aria-roledescription="carousel"
    >
      <span data-testid="carousel-active" className="sr-only">{active.id}</span>
      {active.kind === "master" ? (
        <Link href={`/masters/${active.id}`} className="absolute inset-0">
          <PosterImage src={active.image} alt={active.name} />
          <div className="absolute inset-x-0 bottom-0 bg-gradient-to-t from-black/90 to-transparent p-6">
            <div className="text-[11px] font-semibold uppercase tracking-widest text-tx2">
              {t("masters.title")}
            </div>
            <div className="mt-2 flex items-center gap-3">
              {active.face && (
                // eslint-disable-next-line @next/next/no-img-element
                <img src={active.face} alt={active.name}
                  className="h-12 w-12 rounded-full object-cover ring-1 ring-white/30" />
              )}
              <div>
                <h2 className="text-2xl font-extrabold tracking-tight">{active.name}</h2>
                {active.tagline && <div className="mt-1 text-sm text-tx2">{active.tagline}</div>}
              </div>
            </div>
          </div>
        </Link>
      ) : (
        <ExhibitionCarouselSlide exhibition={active.exhibition as Exhibition} />
      )}

      <div className="absolute right-4 top-4 flex gap-1">
        {slides.map((s, i) => (
          <span key={s.id} aria-hidden="true"
            className={`h-1.5 w-1.5 rounded-full ${i === index ? "bg-white" : "bg-white/40"}`} />
        ))}
      </div>
    </section>
  );
}

function ExhibitionCarouselSlide({ exhibition: e }: { exhibition: Exhibition }) {
  const { t } = useLang();
  return (
    <Link href={`/exhibitions/${e.id}`} className="absolute inset-0">
      <PosterImage src={e.posterImageUrl} alt={e.title} />
      <div className="absolute inset-x-0 bottom-0 bg-gradient-to-t from-black/90 to-transparent p-6">
        <div className="text-[11px] font-semibold uppercase tracking-widest text-tx2">{t("home.featured")}</div>
        <h2 className="mt-2 text-2xl font-extrabold tracking-tight">{e.title}</h2>
        <div className="mt-2 text-sm text-tx2">{e.venue?.name} · {e.startDate}–{e.endDate}</div>
      </div>
    </Link>
  );
}
