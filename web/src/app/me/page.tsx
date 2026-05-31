"use client";
import { useAuth, useBookmarks } from "@/components/AuthProvider";
import { SubscriptionSettings } from "@/components/SubscriptionSettings";
import { FeedbackForm } from "@/components/FeedbackForm";
import { useLang } from "@/components/LanguageProvider";

export default function MePage() {
  const { user, loading, signIn, signOut } = useAuth();
  const { ids } = useBookmarks();
  const { t } = useLang();

  if (loading) return <main className="mx-auto max-w-[680px] px-7 py-16 text-tx3">{t("common.loading")}</main>;
  if (!user) {
    return (
      <main className="mx-auto max-w-[680px] px-7 py-20 text-center">
        <h1 className="text-2xl font-extrabold tracking-tight">{t("me.title")}</h1>
        <p className="mt-3 text-tx2">{t("me.loginPrompt")}</p>
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
    <main className="mx-auto max-w-[680px] px-7 py-10">
      <h1 className="text-[28px] font-extrabold tracking-tight">{t("me.title")}</h1>
      <div className="mt-6 rounded-lg border border-line p-5">
        <div className="text-sm text-tx3">{t("me.account")}</div>
        <div className="mt-1 text-base">{user.email}</div>
        <div className="mt-4 flex items-center gap-6 text-sm text-tx2">
          <span>
            {t("me.scrapCount")} <b className="text-tx">{ids.size}</b>
          </span>
        </div>
      </div>
      <div className="mt-4"><SubscriptionSettings /></div>
      <div className="mt-4"><FeedbackForm /></div>
      <button
        onClick={() => void signOut()}
        className="mt-6 rounded-md border border-line2 px-4 py-2 text-sm font-medium hover:bg-panel2"
      >
        {t("me.signOut")}
      </button>
    </main>
  );
}
