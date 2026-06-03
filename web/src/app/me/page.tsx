"use client";
import { useRouter } from "next/navigation";
import { useAuth, useBookmarks } from "@/components/AuthProvider";
import { SubscriptionSettings } from "@/components/SubscriptionSettings";
import { FeedbackForm } from "@/components/FeedbackForm";
import { useLang } from "@/components/LanguageProvider";
import { useOnboarding } from "@/components/OnboardingProvider";
import { resetOnboarding } from "@/lib/onboarding";

export default function MePage() {
  const { user, loading, signIn, signOut } = useAuth();
  const { ids } = useBookmarks();
  const { t } = useLang();
  const { start } = useOnboarding();
  const router = useRouter();

  function replayTour() {
    resetOnboarding();
    router.push("/");
    start();
  }

  if (loading) return <main className="mx-auto max-w-[680px] px-7 py-16 text-tx3">{t("common.loading")}</main>;

  return (
    <main className="mx-auto max-w-[680px] px-7 py-10">
      <h1 className="text-[28px] font-extrabold tracking-tight">{t("me.title")}</h1>

      {user ? (
        <div className="mt-6 rounded-lg border border-line p-5">
          <div className="text-sm text-tx3">{t("me.account")}</div>
          <div className="mt-1 text-base">{user.email}</div>
          <div className="mt-4 flex items-center gap-6 text-sm text-tx2">
            <span>
              {t("me.scrapCount")} <b className="text-tx">{ids.size}</b>
            </span>
          </div>
        </div>
      ) : (
        <div className="mt-6 rounded-lg border border-line p-5">
          <p className="text-tx2">{t("me.loginPrompt")}</p>
          <button
            onClick={() => void signIn()}
            className="mt-4 rounded-md bg-white px-5 py-2.5 text-sm font-semibold text-black"
          >
            {t("common.signInGoogle")}
          </button>
        </div>
      )}

      <div className="mt-4"><SubscriptionSettings /></div>
      <div className="mt-4"><FeedbackForm /></div>

      <div className="mt-6 flex items-center gap-3">
        <button
          onClick={replayTour}
          className="rounded-md border border-line2 px-4 py-2 text-sm font-medium hover:bg-panel2"
        >
          {t("onb.replay")}
        </button>
        {user && (
          <button
            onClick={() => void signOut()}
            className="rounded-md border border-line2 px-4 py-2 text-sm font-medium hover:bg-panel2"
          >
            {t("me.signOut")}
          </button>
        )}
      </div>
    </main>
  );
}
