"use client";
import Link from "next/link";
import { CinemaSection } from "@/components/CinemaSection";
import { useLang } from "@/components/LanguageProvider";

export default function CinemaPage() {
  const { t } = useLang();
  return (
    <main className="mx-auto max-w-[1180px] px-7 py-10">
      <Link href="/masters" className="text-sm text-tx3 hover:text-tx">← {t("curation.title")}</Link>
      <div className="mt-6">
        <CinemaSection variant="full" />
      </div>
    </main>
  );
}
