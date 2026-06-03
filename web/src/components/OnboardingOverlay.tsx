"use client";
import { ArrowLeft, ArrowRight, Compass, Heart, Layers, Bell, MessageSquare, X } from "lucide-react";
import { useOnboarding } from "@/components/OnboardingProvider";
import { useLang } from "@/components/LanguageProvider";

const STEP_ICON: Record<string, typeof Compass> = {
  welcome: Compass,
  timeline: Layers,
  swipe: Heart,
  scrap: Heart,
  subscribe: Bell,
  feedback: MessageSquare,
};

export function OnboardingOverlay() {
  const { active, step, stepIndex, total, isSwipeStep, next, prev, skip } = useOnboarding();
  const { t } = useLang();

  if (!active || !step) return null;

  const Icon = STEP_ICON[step.id] ?? Compass;
  const isLast = stepIndex >= total - 1;

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
                onClick={next}
                className="rounded-md bg-white px-5 py-2 text-sm font-semibold text-black hover:bg-white/90"
              >
                {isLast ? t("onb.start") : t("onb.next")}
              </button>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
