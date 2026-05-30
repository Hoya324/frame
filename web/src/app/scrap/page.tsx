"use client";
import { useMemo } from "react";
import { loadCatalogSync } from "@/lib/catalogClient";
import { useAuth, useBookmarks } from "@/components/AuthProvider";
import { ExhibitionCard } from "@/components/ExhibitionCard";
import { useLang } from "@/components/LanguageProvider";
import { daysUntil } from "@/lib/status";

export default function ScrapPage() {
  const catalog = loadCatalogSync();
  const { user, loading, signIn } = useAuth();
  const { ids } = useBookmarks();
  const { t } = useLang();
  const today = new Date();

  const saved = useMemo(() => {
    const list = catalog.exhibitions.filter((e) => ids.has(e.id));
    const rank = (d: number | null) => (d == null ? Number.POSITIVE_INFINITY : d < 0 ? 1e6 - d : d);
    return list.sort((a, b) => rank(daysUntil(a.endDate, today)) - rank(daysUntil(b.endDate, today)));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [catalog.exhibitions, ids]);

  if (loading) return <main className="mx-auto max-w-[1180px] px-7 py-16 text-tx3">{t("common.loading")}</main>;
  if (!user) {
    return (
      <main className="mx-auto max-w-[1180px] px-7 py-20 text-center">
        <h1 className="text-2xl font-extrabold tracking-tight">{t("scrap.title")}</h1>
        <p className="mt-3 text-tx2">{t("scrap.loginPrompt")}</p>
        <button
          onClick={() => void signIn()}
          className="mt-6 rounded-md bg-white px-5 py-2.5 text-sm font-semibold text-black"
        >
          {t("common.signInGoogle")}
        </button>
      </main>
    );
  }
  return (
    <main className="mx-auto max-w-[1180px] px-7 py-8">
      <h1 className="text-[28px] font-extrabold tracking-tight">{t("scrap.title")}</h1>
      <p className="mt-2 text-sm text-tx3">{t("scrap.subtitle").replace("{n}", String(saved.length))}</p>
      {saved.length === 0 ? (
        <div className="py-20 text-center text-tx3">{t("scrap.empty")}</div>
      ) : (
        <div className="mt-6 grid grid-cols-2 gap-4 md:grid-cols-4">
          {saved.map((e) => (
            <ExhibitionCard key={e.id} exhibition={e} today={today} />
          ))}
        </div>
      )}
    </main>
  );
}
