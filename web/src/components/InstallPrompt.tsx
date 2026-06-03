"use client";
import { useCallback, useEffect, useState, useSyncExternalStore } from "react";
import { Download, X } from "lucide-react";
import { useLang } from "@/components/LanguageProvider";
import { decidePromptMode, DISMISS_KEY, isDismissActive, isIOS, isSafari } from "@/lib/pwa";
import {
  getCanInstall,
  getServerCanInstall,
  initPwaInstall,
  isStandalone,
  promptInstall,
  subscribeInstall,
} from "@/lib/pwaInstall";

function readDismissedAt(): number | null {
  const raw = localStorage.getItem(DISMISS_KEY);
  const n = raw ? Number(raw) : NaN;
  return Number.isFinite(n) ? n : null;
}

export function InstallPrompt() {
  const { t } = useLang();
  // The captured beforeinstallprompt lives in a shared store so the onboarding
  // step can offer the same one-click install.
  const canInstall = useSyncExternalStore(subscribeInstall, getCanInstall, getServerCanInstall);
  // Static, browser-only environment facts; read once after mount to stay
  // hydration-safe (server renders nothing).
  const [env, setEnv] = useState<{ standalone: boolean; iosSafari: boolean } | null>(null);
  const [dismissed, setDismissed] = useState(false);

  useEffect(() => {
    initPwaInstall();
    const ua = navigator.userAgent;
    // eslint-disable-next-line react-hooks/set-state-in-effect
    setEnv({
      standalone: isStandalone(),
      iosSafari: isIOS(ua, navigator.maxTouchPoints) && isSafari(ua),
    });
    setDismissed(isDismissActive(readDismissedAt(), Date.now()));
  }, []);

  const dismiss = useCallback(() => {
    localStorage.setItem(DISMISS_KEY, String(Date.now()));
    setDismissed(true);
  }, []);

  const install = useCallback(async () => {
    await promptInstall();
    localStorage.setItem(DISMISS_KEY, String(Date.now()));
    setDismissed(true);
  }, []);

  if (!env) return null;

  const mode = decidePromptMode({
    standalone: env.standalone,
    dismissed,
    hasDeferredPrompt: canInstall,
    iosSafari: env.iosSafari,
  });

  if (mode === "none") return null;

  return (
    <div className="fixed inset-x-0 bottom-[76px] z-30 px-4 md:bottom-4">
      <div className="mx-auto flex max-w-[480px] animate-[slideUp_.3s_cubic-bezier(.22,.61,.36,1)] items-center gap-3 rounded-2xl border border-line2 bg-panel2 p-3.5 shadow-2xl">
        <div className="grid h-10 w-10 shrink-0 place-items-center rounded-xl bg-white text-black">
          <Download size={20} />
        </div>
        <div className="min-w-0 flex-1">
          <p className="truncate text-sm font-semibold text-tx">{t("pwa.title")}</p>
          <p className="truncate text-xs text-tx2">
            {mode === "ios" ? t("pwa.iosHint") : t("pwa.desc")}
          </p>
        </div>
        {mode === "install" && (
          <button
            onClick={install}
            className="shrink-0 rounded-lg bg-white px-3.5 py-2 text-sm font-semibold text-black hover:bg-white/90"
          >
            {t("pwa.install")}
          </button>
        )}
        <button
          onClick={dismiss}
          aria-label={t("pwa.dismiss")}
          className="shrink-0 rounded-lg p-1.5 text-tx3 hover:text-tx"
        >
          <X size={18} />
        </button>
      </div>
    </div>
  );
}
