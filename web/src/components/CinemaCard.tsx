"use client";
import Link from "next/link";
import { useLang } from "@/components/LanguageProvider";
import type { CinemaScene } from "@/lib/cinema";

// One film card — opens its detail page. Modern (in-copyright) entries carry a
// © studio credit; PD entries don't.
export function CinemaCard({ scene }: { scene: CinemaScene }) {
  const { locale } = useLang();
  return (
    <Link
      href={`/masters/cinema/${scene.id}`}
      className="group block overflow-hidden rounded border border-line transition-colors hover:border-line2"
    >
      <div className="relative aspect-[4/3] bg-panel2">
        {/* eslint-disable-next-line @next/next/no-img-element */}
        <img src={scene.image} alt={scene.title[locale]} loading="lazy" className="h-full w-full object-cover" />
      </div>
      <div className="p-3">
        <div className="font-semibold tracking-tight">{scene.title[locale]}</div>
        <div className="text-[12px] text-tx3">{scene.credit[locale]}</div>
        <p className="mt-1 line-clamp-3 text-[13px] leading-snug text-tx2">{scene.lesson[locale]}</p>
        {scene.studio && <div className="mt-2 text-[11px] text-tx3">© {scene.studio}</div>}
      </div>
    </Link>
  );
}
