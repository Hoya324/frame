"use client";
import Link from "next/link";
import { useLang } from "@/components/LanguageProvider";
import type { CinemaScene } from "@/lib/cinema";

// Detail page for one film: hero + gallery of stills, a longer curation, the
// "what to learn" note, and (for modern in-copyright films) a © studio credit
// plus the 인용 disclaimer. Links out to the film's TMDB page.
export function CinemaDetailView({ scene }: { scene: CinemaScene }) {
  const { t, locale } = useLang();
  const stills = scene.gallery && scene.gallery.length ? scene.gallery : (scene.image ? [scene.image] : []);
  const hero = stills[0];
  const rest = stills.slice(1);
  const body = scene.curation?.[locale] || scene.lesson[locale];

  return (
    <main className="mx-auto max-w-[900px] px-7 py-10">
      <Link href="/masters/cinema" className="text-sm text-tx3 hover:text-tx">← {t("cinema.title")}</Link>

      <h1 className="mt-5 text-[28px] font-extrabold leading-tight tracking-tight">{scene.title[locale]}</h1>
      <div className="mt-1 text-sm text-tx3">{scene.credit[locale]}</div>

      {hero && (
        <div className="mt-6 overflow-hidden rounded border border-line bg-panel2">
          {/* eslint-disable-next-line @next/next/no-img-element */}
          <img src={hero} alt={scene.title[locale]} className="w-full object-cover" />
        </div>
      )}

      <p className="mt-6 text-[15px] leading-relaxed text-tx">{body}</p>

      <div className="mt-5 rounded border border-line bg-panel p-4">
        <div className="text-[12px] font-semibold uppercase tracking-wide text-tx3">
          {t("cinema.lessonLabel")}
        </div>
        <p className="mt-1.5 text-[14px] leading-relaxed text-tx2">{scene.lesson[locale]}</p>
      </div>

      {rest.length > 0 && (
        <div className="mt-6 grid grid-cols-1 gap-3 sm:grid-cols-2">
          {rest.map((src, i) => (
            <div key={i} className="overflow-hidden rounded border border-line bg-panel2">
              {/* eslint-disable-next-line @next/next/no-img-element */}
              <img src={src} alt={`${scene.title[locale]} ${i + 2}`} loading="lazy"
                className="w-full object-cover" />
            </div>
          ))}
        </div>
      )}

      <div className="mt-7 flex flex-wrap items-center justify-between gap-3 border-t border-line pt-5">
        <div className="text-[12px] text-tx3">
          {scene.studio && <span>© {scene.studio} · </span>}
          {scene.studio ? t("cinema.modernNote") : "Public domain"}
        </div>
        <a href={scene.url} target="_blank" rel="noopener noreferrer"
          className="shrink-0 text-[13px] text-tx2 hover:text-tx">
          {t("cinema.viewMore")} ↗
        </a>
      </div>
    </main>
  );
}
