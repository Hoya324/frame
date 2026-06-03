"use client";
import { useEffect, useMemo, useState, useSyncExternalStore } from "react";
import { Download } from "lucide-react";
import { useLang } from "@/components/LanguageProvider";
import { isIOS, isSafari } from "@/lib/pwa";
import { EVENTS, track } from "@/lib/analytics";
import {
  getCanInstall,
  getServerCanInstall,
  initPwaInstall,
  isStandalone,
  promptInstall,
  subscribeInstall,
} from "@/lib/pwaInstall";

// Persistent "install the app" entry point for the My page — a permanent home
// for the same one-click install the onboarding offers (so people who skipped
// onboarding or dismissed the floating banner can still install anytime).
export function InstallAppCard() {
  const { t } = useLang();
  useEffect(() => initPwaInstall(), []);
  const canInstall = useSyncExternalStore(subscribeInstall, getCanInstall, getServerCanInstall);
  const env = useMemo(() => {
    if (typeof navigator === "undefined") return { iosSafari: false, standalone: false };
    const ua = navigator.userAgent;
    return {
      iosSafari: isIOS(ua, navigator.maxTouchPoints) && isSafari(ua),
      standalone: isStandalone(),
    };
  }, []);
  const [installing, setInstalling] = useState(false);
  const [installed, setInstalled] = useState(false);

  // Already running as the installed app — nothing to offer.
  if (env.standalone || installed) return null;

  const onInstall = async () => {
    setInstalling(true);
    try {
      const result = await promptInstall();
      track(EVENTS.pwaInstallPrompt, { result, source: "me" });
      if (result === "accepted") setInstalled(true);
    } finally {
      setInstalling(false);
    }
  };

  // When no one-click prompt is available it's either iOS Safari (manual steps)
  // or a desktop browser where the app may already be installed — keep the hint
  // neutral so it doesn't tell an existing installer to "install" again.
  const hint = env.iosSafari ? t("pwa.iosHint") : t("onb.install.manual");

  return (
    <div className="rounded-lg border border-line p-5">
      <div className="flex items-center gap-3">
        <div className="grid h-10 w-10 shrink-0 place-items-center rounded-xl bg-white text-black">
          <Download size={20} />
        </div>
        <div className="min-w-0 flex-1">
          <div className="text-sm font-medium">{t("onb.install.title")}</div>
          <div className="text-xs text-tx3">{t("onb.install.body")}</div>
        </div>
        {canInstall && (
          <button
            type="button"
            onClick={() => void onInstall()}
            disabled={installing}
            className="inline-flex shrink-0 items-center gap-1.5 rounded-md bg-white px-4 py-2 text-sm font-semibold text-black hover:bg-white/90 disabled:opacity-60"
          >
            <Download size={15} />
            {t("pwa.install")}
          </button>
        )}
      </div>
      {!canInstall && <p className="mt-3 text-xs text-tx3">{hint}</p>}
    </div>
  );
}
