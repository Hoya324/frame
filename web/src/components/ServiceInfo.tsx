"use client";
import { useLang } from "@/components/LanguageProvider";

// Bumped manually with each release; mirrors web/package.json "version".
const APP_VERSION = "0.1.0";
const GITHUB_URL = "https://github.com/Hoya324";
const INSTAGRAM_URL = "https://instagram.com/_onhosi";
const LICENSE_URL = "https://github.com/Hoya324/frame/blob/main/LICENSE";

export function ServiceInfo() {
  const { t } = useLang();

  return (
    <section className="rounded-lg border border-line p-5">
      <div className="text-sm text-tx3">{t("svc.title")}</div>

      <div className="mt-4">
        <div className="text-xs font-medium text-tx2">{t("svc.appInfo")}</div>
        <div className="mt-1.5 flex items-center justify-between text-sm">
          <span className="text-tx">FRAME</span>
          <span className="text-tx3">v{APP_VERSION}</span>
        </div>
      </div>

      <div className="mt-4 border-t border-line pt-4">
        <div className="text-xs font-medium text-tx2">{t("svc.license")}</div>
        <p className="mt-1.5 text-sm leading-relaxed text-tx2">{t("svc.licenseBody")}</p>
        <a
          href={LICENSE_URL}
          target="_blank"
          rel="noreferrer"
          className="mt-1.5 inline-block text-sm text-tx underline underline-offset-2 hover:text-tx2"
        >
          {t("svc.licenseView")}
        </a>
      </div>

      <div className="mt-4 border-t border-line pt-4">
        <div className="text-xs font-medium text-tx2">{t("svc.developer")}</div>
        <div className="mt-2 flex flex-col gap-2 text-sm">
          <a
            href={GITHUB_URL}
            target="_blank"
            rel="noreferrer"
            className="flex items-center justify-between hover:text-tx"
          >
            <span className="text-tx3">GitHub</span>
            <span className="text-tx">@Hoya324</span>
          </a>
          <a
            href={INSTAGRAM_URL}
            target="_blank"
            rel="noreferrer"
            className="flex items-center justify-between hover:text-tx"
          >
            <span className="text-tx3">Instagram</span>
            <span className="text-tx">@_onhosi</span>
          </a>
        </div>
      </div>
    </section>
  );
}
