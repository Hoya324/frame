"use client";
import { useEffect, useMemo, useRef, useState } from "react";
import Link from "next/link";
import { PosterImage } from "@/components/PosterImage";
import { useLang } from "@/components/LanguageProvider";
import { buildCarouselSlides, type CarouselSlide, type CinemaSlide, type MasterSlide } from "@/lib/carousel";
import type { Master } from "@/lib/masters";
import type { CinemaScene } from "@/lib/cinema";
import type { Exhibition } from "@/lib/catalog";
import type { Locale } from "@/lib/i18n";

// Auto-advance interval. Slow enough to read each slide's caption.
const ADVANCE_MS = 4500;
const FADE_MS = 900;

type T = (key: string) => string;

function prefersReducedMotion(): boolean {
  return typeof window !== "undefined"
    && window.matchMedia?.("(prefers-reduced-motion: reduce)").matches === true;
}

export function FeaturedCarousel({
  exhibitions,
  masters,
  cinema = [],
  masterCount = 6,
  cinemaCount = 4,
  rng,
}: {
  exhibitions: Exhibition[];
  masters: Master[];
  cinema?: CinemaScene[];
  masterCount?: number;
  cinemaCount?: number;
  rng?: () => number;
}) {
  const { t, locale } = useLang();
  // Build the slide list once per mount so it stays stable while advancing, but
  // is reshuffled (random masters/cinema) on each fresh load.
  const slides = useMemo<CarouselSlide[]>(
    () => buildCarouselSlides(exhibitions, masters, { masterCount, cinema, cinemaCount, rng }),
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
      className="relative mb-9 min-h-[320px] overflow-hidden rounded border border-line bg-panel2"
      onMouseEnter={() => setPaused(true)}
      onMouseLeave={() => setPaused(false)}
      onFocusCapture={() => setPaused(true)}
      onBlurCapture={() => setPaused(false)}
      aria-roledescription="carousel"
    >
      <span data-testid="carousel-active" className="sr-only">{active.id}</span>

      {/* All slides are stacked and cross-fade; rendering them all also warms the
          image cache so transitions are instant. */}
      {slides.map((s, i) => {
        const isActive = i === index;
        return (
          <div
            key={s.id}
            aria-hidden={!isActive}
            style={{ transitionDuration: `${FADE_MS}ms` }}
            className={`absolute inset-0 transition-opacity ease-out motion-reduce:transition-none ${
              isActive ? "z-10 opacity-100" : "pointer-events-none opacity-0"
            }`}
          >
            {s.kind === "master"
              ? <MasterCarouselSlide slide={s} active={isActive} t={t} />
              : s.kind === "cinema"
              ? <CinemaCarouselSlide slide={s} active={isActive} t={t} locale={locale} />
              : <ExhibitionCarouselSlide exhibition={s.exhibition as Exhibition} active={isActive} t={t} />}
          </div>
        );
      })}

      {/* Indicators — clickable, with the active one stretched into a pill. */}
      <div className="absolute right-4 top-4 z-20 flex items-center gap-1.5">
        {slides.map((s, i) => (
          <button
            key={s.id}
            type="button"
            aria-label={`슬라이드 ${i + 1}`}
            aria-current={i === index}
            onClick={() => setIndex(i)}
            className={`h-1.5 rounded-full transition-all duration-300 ${
              i === index ? "w-5 bg-white" : "w-1.5 bg-white/40 hover:bg-white/70"
            }`}
          />
        ))}
      </div>
    </section>
  );
}

// A slow zoom (Ken Burns) on the active slide's image gives the still a sense of
// life; it eases back to neutral while inactive.
function zoomClass(active: boolean): string {
  return `absolute inset-0 transition-transform ease-out duration-[6000ms] motion-reduce:transition-none ${
    active ? "scale-110" : "scale-100"
  }`;
}

// The caption rises and fades in as its slide becomes active.
function captionClass(active: boolean): string {
  return `absolute inset-x-0 bottom-0 bg-gradient-to-t from-black/90 to-transparent p-6 transition-all duration-700 ease-out motion-reduce:transition-none ${
    active ? "translate-y-0 opacity-100" : "translate-y-3 opacity-0"
  }`;
}

function MasterCarouselSlide({ slide, active, t }: { slide: MasterSlide; active: boolean; t: T }) {
  return (
    <Link href={`/masters/${slide.id}`} className="absolute inset-0" tabIndex={active ? 0 : -1}>
      <div className={zoomClass(active)}>
        <PosterImage src={slide.image} alt={slide.name} />
      </div>
      <div className={captionClass(active)}>
        <div className="text-[11px] font-semibold uppercase tracking-widest text-tx2">
          {t("masters.title")}
        </div>
        <div className="mt-2 flex items-center gap-3">
          {slide.face && (
            // eslint-disable-next-line @next/next/no-img-element
            <img src={slide.face} alt={slide.name} loading="lazy"
              className="h-12 w-12 rounded-full object-cover ring-1 ring-white/30" />
          )}
          <div>
            <h2 className="text-2xl font-extrabold tracking-tight">{slide.name}</h2>
            {slide.tagline && <div className="mt-1 text-sm text-tx2">{slide.tagline}</div>}
          </div>
        </div>
      </div>
    </Link>
  );
}

function CinemaCarouselSlide({ slide, active, t, locale }: {
  slide: CinemaSlide; active: boolean; t: T; locale: Locale;
}) {
  return (
    <Link href="/masters/cinema" className="absolute inset-0" tabIndex={active ? 0 : -1}>
      <div className={zoomClass(active)}>
        <PosterImage src={slide.image} alt={slide.title[locale]} />
      </div>
      <div className={captionClass(active)}>
        <div className="text-[11px] font-semibold uppercase tracking-widest text-tx2">
          {t("cinema.title")}
        </div>
        <h2 className="mt-2 text-2xl font-extrabold tracking-tight">{slide.title[locale]}</h2>
        <div className="mt-1 text-sm text-tx2">{slide.credit[locale]}</div>
      </div>
    </Link>
  );
}

function ExhibitionCarouselSlide({ exhibition: e, active, t }: { exhibition: Exhibition; active: boolean; t: T }) {
  return (
    <Link href={`/exhibitions/${e.id}`} className="absolute inset-0" tabIndex={active ? 0 : -1}>
      <div className={zoomClass(active)}>
        <PosterImage src={e.posterImageUrl} alt={e.title} />
      </div>
      <div className={captionClass(active)}>
        <div className="text-[11px] font-semibold uppercase tracking-widest text-tx2">{t("home.featured")}</div>
        <h2 className="mt-2 text-2xl font-extrabold tracking-tight">{e.title}</h2>
        <div className="mt-2 text-sm text-tx2">{e.venue?.name} · {e.startDate}–{e.endDate}</div>
      </div>
    </Link>
  );
}
