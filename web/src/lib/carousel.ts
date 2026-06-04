import type { Master } from "@/lib/masters";
import { masterFaceImage, masterHeroImage } from "@/lib/masters";

export interface ExhibitionSlide {
  kind: "exhibition";
  id: string;
  exhibition: unknown; // the caller's Exhibition; kept opaque here
}

export interface MasterSlide {
  kind: "master";
  id: string;
  name: string;
  tagline: string | null;
  image: string;        // representative work (background)
  face: string | null;  // portrait
}

export type CarouselSlide = ExhibitionSlide | MasterSlide;

export interface BuildOptions {
  masterCount?: number;
  rng?: () => number; // returns [0,1); defaults to Math.random
}

// Fisher–Yates using the injected rng so tests are deterministic.
function shuffle<T>(items: T[], rng: () => number): T[] {
  const a = [...items];
  for (let i = a.length - 1; i > 0; i--) {
    const j = Math.floor(rng() * (i + 1));
    [a[i], a[j]] = [a[j], a[i]];
  }
  return a;
}

export function buildCarouselSlides(
  exhibitions: Array<{ id: string }>,
  masters: Master[],
  opts: BuildOptions = {},
): CarouselSlide[] {
  const rng = opts.rng ?? Math.random;
  const masterCount = opts.masterCount ?? 6;

  const exhibitionSlides: ExhibitionSlide[] = exhibitions.map((e) => ({
    kind: "exhibition", id: e.id, exhibition: e,
  }));

  const usable = masters.filter((m) => masterHeroImage(m));
  const masterSlides: MasterSlide[] = shuffle(usable, rng)
    .slice(0, masterCount)
    .map((m) => ({
      kind: "master", id: m.id, name: m.name, tagline: m.tagline,
      image: masterHeroImage(m) as string, face: masterFaceImage(m),
    }));

  // Interleave so masters and exhibitions alternate where possible, then keep
  // any leftovers. The whole sequence is shuffled by rng for variety per load.
  return shuffle([...exhibitionSlides, ...masterSlides], rng);
}
