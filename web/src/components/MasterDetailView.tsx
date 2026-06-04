"use client";
import Link from "next/link";
import { PosterImage } from "@/components/PosterImage";
import { useLang } from "@/components/LanguageProvider";
import { inLocale } from "@/lib/catalog";
import type { Locale } from "@/lib/i18n";
import type { Master, MasterWork } from "@/lib/masters";

export function MasterDetailView({ master }: { master: Master }) {
  const { t, locale } = useLang();
  const name = inLocale(master.name, master.tr, locale, "name");
  const bio = inLocale(master.bio, master.tr, locale, "bio");
  const years = master.birthYear
    ? t("masters.years", { birth: master.birthYear, death: master.deathYear ?? "" })
    : "";

  return (
    <main className="mx-auto max-w-[900px] px-7 py-10">
      <Link href="/masters" className="text-sm text-tx3 hover:text-tx">← {t("masters.title")}</Link>
      <header className="mt-4 flex items-center gap-4">
        {master.portraitUrl && (
          // eslint-disable-next-line @next/next/no-img-element
          <img src={master.portraitUrl} alt={name}
            className="h-16 w-16 rounded-full object-cover ring-1 ring-line" />
        )}
        <div>
          <h1 className="text-[28px] font-extrabold tracking-tight">{name}</h1>
          <div className="text-sm text-tx3">
            {years}{master.nationality ? ` · ${master.nationality}` : ""}
          </div>
        </div>
      </header>
      {bio && <p className="mt-4 text-[15px] leading-relaxed text-tx2">{bio}</p>}

      <div className="mt-10 space-y-12">
        {master.works.map((w) => <WorkBlock key={w.id} w={w} locale={locale} t={t} />)}
      </div>
    </main>
  );
}

function WorkBlock({ w, locale, t }: {
  w: MasterWork; locale: Locale; t: (k: string, v?: Record<string, string | number>) => string;
}) {
  const title = inLocale(w.title, w.tr, locale, "title");
  const commentary = inLocale(w.commentary, w.tr, locale, "commentary");
  return (
    <article>
      {/* PosterImage uses next/image `fill`, so it needs a positioned + sized
          parent — give the link a relative box with an aspect ratio. */}
      <a href={w.sourceUrl ?? "#"} target="_blank" rel="noreferrer"
        className="relative block aspect-[4/3] w-full overflow-hidden rounded bg-black/30">
        <PosterImage src={w.imageUrl} alt={title} />
      </a>
      <div className="mt-3">
        <div className="font-semibold tracking-tight">{title}</div>
        <div className="text-[13px] text-tx3">
          {[w.year, w.medium].filter(Boolean).join(" · ")}
        </div>
        {commentary && (
          <div className="mt-3">
            <div className="text-[11px] font-semibold uppercase tracking-widest text-tx3">
              {t("masters.whyGreat")}
            </div>
            <p className="mt-1 text-[14px] leading-relaxed text-tx2">{commentary}</p>
          </div>
        )}
        <div className="mt-2 text-[12px] text-tx3">
          {t("masters.source")}: {w.credit}{w.sourceUrl ? " · " : ""}
          {w.sourceUrl && (
            <a href={w.sourceUrl} target="_blank" rel="noreferrer" className="underline hover:text-tx">
              {t("masters.viewOriginal")}
            </a>
          )}
        </div>
      </div>
    </article>
  );
}
