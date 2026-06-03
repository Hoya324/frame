"use client";
import { useEffect, useMemo, useState, useSyncExternalStore } from "react";
import { ArrowLeft, ArrowRight, Compass, Download, Heart, Layers, Bell, MessageSquare, X } from "lucide-react";
import { useOnboarding } from "@/components/OnboardingProvider";
import { useLang } from "@/components/LanguageProvider";
import { isIOS, isSafari } from "@/lib/pwa";
import {
  getCanInstall,
  getServerCanInstall,
  initPwaInstall,
  isStandalone,
  promptInstall,
  subscribeInstall,
} from "@/lib/pwaInstall";

const STEP_ICON: Record<string, typeof Compass> = {
  welcome: Compass,
  timeline: Layers,
  swipe: Heart,
  scrap: Heart,
  subscribe: Bell,
  feedback: MessageSquare,
  install: Download,
};

export function OnboardingOverlay() {
  const { active, step, stepIndex, total, isSwipeStep, isInstallStep, next, prev, skip } = useOnboarding();
  const { t } = useLang();

  // PWA install availability (shared store) — drives the one-click install button.
  useEffect(() => initPwaInstall(), []);
  const canInstall = useSyncExternalStore(subscribeInstall, getCanInstall, getServerCanInstall);
  const installEnv = useMemo(() => {
    if (typeof navigator === "undefined") return { iosSafari: false, standalone: false };
    const ua = navigator.userAgent;
    return {
      iosSafari: isIOS(ua, navigator.maxTouchPoints) && isSafari(ua),
      standalone: isStandalone(),
    };
  }, []);
  const [installing, setInstalling] = useState(false);

  if (!active || !step) return null;

  const Icon = STEP_ICON[step.id] ?? Compass;
  const isLast = stepIndex >= total - 1;

  // On the install step, the primary button triggers the real native install
  // when available; otherwise it just finishes the tour.
  const onPrimary = async () => {
    if (isInstallStep && canInstall) {
      setInstalling(true);
      try {
        await promptInstall();
      } finally {
        setInstalling(false);
      }
    }
    next();
  };
  const primaryLabel = isInstallStep
    ? canInstall
      ? t("pwa.install")
      : t("onb.done")
    : isLast
      ? t("onb.start")
      : t("onb.next");

  return (
    <div
      className="fixed inset-0 z-50 flex flex-col justify-end bg-gradient-to-t from-black/80 via-black/45 to-black/30 animate-[fadeIn_.2s_ease]"
      role="dialog"
      aria-modal="true"
      aria-label={t(step.titleKey)}
    >
      <button
        type="button"
        onClick={skip}
        aria-label={t("onb.skip")}
        className="absolute right-4 top-4 flex h-9 w-9 items-center justify-center rounded-full border border-line2 bg-black/40 text-tx2 hover:text-tx"
      >
        <X size={18} />
      </button>

      <div className="mx-auto mb-[96px] w-full max-w-[460px] px-5 md:mb-10">
        <div className="animate-[slideUp_.3s_cubic-bezier(.22,.61,.36,1)] rounded-2xl border border-line2 bg-panel2 p-6 shadow-2xl">
          <div className="grid h-12 w-12 place-items-center rounded-xl bg-white text-black">
            <Icon size={24} />
          </div>

          <h2 className="mt-4 text-xl font-extrabold tracking-tight text-tx">{t(step.titleKey)}</h2>
          <p className="mt-2 text-sm leading-relaxed text-tx2">{t(step.bodyKey)}</p>

          {isSwipeStep && (
            <div className="mt-4 flex items-center justify-center gap-6 rounded-xl border border-line bg-black/40 py-4">
              <div className="flex flex-col items-center gap-1 text-rose-400 animate-[swipeHintLeft_1.4s_ease-in-out_infinite]">
                <ArrowLeft size={22} />
                <span className="text-xs font-medium">{t("swipe.skip")}</span>
              </div>
              <div className="grid h-12 w-9 place-items-center rounded-lg border border-line2 text-tx3">
                <Layers size={16} />
              </div>
              <div className="flex flex-col items-center gap-1 text-emerald-400 animate-[swipeHintRight_1.4s_ease-in-out_infinite]">
                <ArrowRight size={22} />
                <span className="text-xs font-medium">{t("scrap.add")}</span>
              </div>
            </div>
          )}

          {isInstallStep && (
            <div className="mt-4 rounded-xl border border-line bg-black/40 px-4 py-3 text-xs leading-relaxed text-tx2">
              {installEnv.standalone
                ? t("onb.install.already")
                : canInstall
                  ? t("onb.install.oneClick")
                  : installEnv.iosSafari
                    ? t("pwa.iosHint")
                    : t("onb.install.manual")}
            </div>
          )}

          {/* step dots */}
          <div className="mt-5 flex items-center gap-1.5" aria-hidden="true">
            {Array.from({ length: total }).map((_, i) => (
              <span
                key={i}
                className={`h-1.5 rounded-full transition-all ${
                  i === stepIndex ? "w-5 bg-white" : "w-1.5 bg-line2"
                }`}
              />
            ))}
          </div>

          <div className="mt-5 flex items-center justify-between gap-3">
            <button
              type="button"
              onClick={skip}
              className="text-sm font-medium text-tx3 hover:text-tx"
            >
              {t("onb.skip")}
            </button>
            <div className="flex items-center gap-2">
              {stepIndex > 0 && (
                <button
                  type="button"
                  onClick={prev}
                  className="rounded-md border border-line2 px-4 py-2 text-sm font-medium hover:bg-panel"
                >
                  {t("onb.prev")}
                </button>
              )}
              <button
                type="button"
                onClick={() => void onPrimary()}
                disabled={installing}
                className="inline-flex items-center gap-1.5 rounded-md bg-white px-5 py-2 text-sm font-semibold text-black hover:bg-white/90 disabled:opacity-60"
              >
                {isInstallStep && canInstall && <Download size={15} />}
                {primaryLabel}
              </button>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
