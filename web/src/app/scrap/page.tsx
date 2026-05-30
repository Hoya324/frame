"use client";
import { useMemo } from "react";
import { loadCatalogSync } from "@/lib/catalogClient";
import { useAuth, useBookmarks } from "@/components/AuthProvider";
import { ExhibitionCard } from "@/components/ExhibitionCard";
import { daysUntil } from "@/lib/status";

export default function ScrapPage() {
  const catalog = loadCatalogSync();
  const { user, loading, signIn } = useAuth();
  const { ids } = useBookmarks();
  const today = new Date();

  const saved = useMemo(() => {
    const list = catalog.exhibitions.filter((e) => ids.has(e.id));
    const rank = (d: number | null) => (d == null ? Number.POSITIVE_INFINITY : d < 0 ? 1e6 - d : d);
    return list.sort((a, b) => rank(daysUntil(a.endDate, today)) - rank(daysUntil(b.endDate, today)));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [catalog.exhibitions, ids]);

  if (loading) return <main className="mx-auto max-w-[1180px] px-7 py-16 text-tx3">불러오는 중…</main>;
  if (!user) {
    return (
      <main className="mx-auto max-w-[1180px] px-7 py-20 text-center">
        <h1 className="text-2xl font-extrabold tracking-tight">스크랩</h1>
        <p className="mt-3 text-tx2">로그인하면 마음에 드는 전시를 저장할 수 있어요.</p>
        <button
          onClick={() => void signIn()}
          className="mt-6 rounded-md bg-white px-5 py-2.5 text-sm font-semibold text-black"
        >
          Google로 로그인
        </button>
      </main>
    );
  }
  return (
    <main className="mx-auto max-w-[1180px] px-7 py-8">
      <h1 className="text-[28px] font-extrabold tracking-tight">스크랩</h1>
      <p className="mt-2 text-sm text-tx3">{saved.length}건 · 종료 임박순</p>
      {saved.length === 0 ? (
        <div className="py-20 text-center text-tx3">아직 스크랩한 전시가 없어요</div>
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
