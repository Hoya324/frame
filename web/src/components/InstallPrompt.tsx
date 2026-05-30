"use client";
import { useCallback, useEffect, useRef, useState } from "react";
import { Download, X } from "lucide-react";
import { useLang } from "@/components/LanguageProvider";
import {
  decidePromptMode,
  DISMISS_KEY,
  isDismissActive,
  isIOS,
  isSafari,
  type PromptMode,
} from "@/lib/pwa";

interface BeforeInstallPromptEvent extends Event {
  prompt: () => Promise<void>;
  userChoice: Promise<{ outcome: "accepted" | "dismissed" }>;
}

function readDismissedAt(): number | null {
  const raw = localStorage.getItem(DISMISS_KEY);
  const n = raw ? Number(raw) : NaN;
  return Number.isFinite(n) ? n : null;
}

function isStandalone(): boolean {
  return (
    window.matchMedia("(display-mode: standalone)").matches ||
    (window.navigator as { standalone?: boolean }).standalone === true
  );
}

export function InstallPrompt() {
  const { t } = useLang();
  const [mode, setMode] = useState<PromptMode>("none");
  const deferred = useRef<BeforeInstallPromptEvent | null>(null);

  useEffect(() => {
    const standalone = isStandalone();
    const dismissed = isDismissActive(readDismissedAt(), Date.now());
    const ua = navigator.userAgent;
    const iosSafari = isIOS(ua, navigator.maxTouchPoints) && isSafari(ua);

    // Read once after mount: these depend on browser-only APIs, and deferring
    // past hydration is what keeps the prerendered (null) markup consistent.
    // eslint-disable-next-line react-hooks/set-state-in-effect
    setMode(
      decidePromptMode({ standalone, dismissed, hasDeferredPrompt: false, iosSafari }),
    );

    const onBeforeInstall = (e: Event) => {
      e.preventDefault();
      deferred.current = e as BeforeInstallPromptEvent;
      setMode(
        decidePromptMode({ standalone, dismissed, hasDeferredPrompt: true, iosSafari }),
      );
    };
    const onInstalled = () => {
      deferred.current = null;
      localStorage.setItem(DISMISS_KEY, String(Date.now()));
      setMode("none");
    };

    window.addEventListener("beforeinstallprompt", onBeforeInstall);
    window.addEventListener("appinstalled", onInstalled);
    return () => {
      window.removeEventListener("beforeinstallprompt", onBeforeInstall);
      window.removeEventListener("appinstalled", onInstalled);
    };
  }, []);

  const dismiss = useCallback(() => {
    localStorage.setItem(DISMISS_KEY, String(Date.now()));
    setMode("none");
  }, []);

  const install = useCallback(async () => {
    const evt = deferred.current;
    if (!evt) return;
    await evt.prompt();
    await evt.userChoice;
    deferred.current = null;
    localStorage.setItem(DISMISS_KEY, String(Date.now()));
    setMode("none");
  }, []);

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
