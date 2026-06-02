import type { FieldTr, JobExhibition, Locale } from "./catalog";

function esc(s: string): string {
  return s.replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]!));
}

// Localized chrome (section titles + subjects) per locale. Content (titles,
// venues) is translated from the catalog; this is only the email's own copy.
interface EmailStrings {
  digestTitle: string; closingTitle: string; customTitle: string;
  digestSubject: string; closingSubject: string; customSubject: string;
}
const STRINGS: Record<Locale, EmailStrings> = {
  ko: {
    digestTitle: "이번 주의 전시", closingTitle: "스크랩한 전시가 곧 끝나요",
    customTitle: "관심 조건에 맞는 새 전시",
    digestSubject: "FRAME 주간 다이제스트", closingSubject: "곧 종료되는 스크랩 전시",
    customSubject: "관심 조건에 맞는 새 전시",
  },
  en: {
    digestTitle: "Exhibitions this week", closingTitle: "Your saved exhibitions are closing soon",
    customTitle: "New exhibitions matching your interests",
    digestSubject: "FRAME Weekly Digest", closingSubject: "Saved exhibitions closing soon",
    customSubject: "New exhibitions matching your interests",
  },
  ja: {
    digestTitle: "今週の展示", closingTitle: "保存した展示がまもなく終了します",
    customTitle: "関心に合う新着展示",
    digestSubject: "FRAME ウィークリーダイジェスト", closingSubject: "まもなく終了する保存展示",
    customSubject: "関心に合う新着展示",
  },
};

export function emailStrings(locale: Locale): EmailStrings {
  return STRINGS[locale] ?? STRINGS.ko;
}

// The user-locale text plus, when a translation exists and differs, the
// original underneath. When there is no translation (or it equals the
// original), only the original shows — it is already in its own language.
function bilingual(original: string, tr: FieldTr, locale: Locale): { primary: string; secondary: string | null } {
  const t = tr[locale];
  if (t && t !== original) return { primary: t, secondary: original };
  return { primary: original, secondary: null };
}

function card(e: JobExhibition, siteUrl: string, locale: Locale, badge?: string): string {
  const url = `${siteUrl}/exhibitions/${encodeURIComponent(e.id)}`;
  const title = bilingual(e.title, e.titleTr, locale);
  const venue = e.venueName ? bilingual(e.venueName, e.venueNameTr, locale) : null;
  const sub = [venue?.primary, e.region].filter(Boolean).map((s) => esc(s!)).join(" · ");
  const origLine = [venue?.secondary, title.secondary].filter(Boolean).map((s) => esc(s!)).join(" · ");
  return `
    <tr><td style="padding:12px 0;border-bottom:1px solid #222;">
      <a href="${url}" style="color:#fff;text-decoration:none;font-weight:700;font-size:16px;">
        ${badge ? `<span style="background:#fff;color:#000;border-radius:999px;padding:2px 8px;font-size:11px;margin-right:8px;">${esc(badge)}</span>` : ""}${esc(title.primary)}
      </a>
      <div style="color:#9a9a9a;font-size:13px;margin-top:4px;">${sub}</div>
      ${origLine ? `<div style="color:#6a6a6a;font-size:12px;margin-top:2px;">${origLine}</div>` : ""}
    </td></tr>`;
}

function shell(title: string, body: string, locale: Locale): string {
  return `<!doctype html><html lang="${locale}"><body style="margin:0;background:#000;color:#fff;font-family:-apple-system,BlinkMacSystemFont,Helvetica,Arial,sans-serif;">
    <table width="100%" cellpadding="0" cellspacing="0" style="max-width:560px;margin:0 auto;padding:28px;">
      <tr><td style="font-weight:800;font-size:22px;letter-spacing:-0.03em;padding-bottom:8px;">FRAME</td></tr>
      <tr><td style="color:#9a9a9a;font-size:14px;padding-bottom:16px;">${esc(title)}</td></tr>
      ${body}
    </table></body></html>`;
}

export function renderDigest(items: JobExhibition[], siteUrl: string, locale: Locale = "ko"): string {
  const rows = items.map((e) => card(e, siteUrl, locale)).join("");
  return shell(emailStrings(locale).digestTitle, `<tr><td><table width="100%">${rows}</table></td></tr>`, locale);
}

export function renderClosingSoon(
  items: { e: JobExhibition; dday: number }[], siteUrl: string, locale: Locale = "ko",
): string {
  const rows = items.map(({ e, dday }) => card(e, siteUrl, locale, `D-${dday}`)).join("");
  return shell(emailStrings(locale).closingTitle, `<tr><td><table width="100%">${rows}</table></td></tr>`, locale);
}

export function renderCustom(items: JobExhibition[], siteUrl: string, locale: Locale = "ko"): string {
  const rows = items.map((e) => card(e, siteUrl, locale, "NEW")).join("");
  return shell(emailStrings(locale).customTitle, `<tr><td><table width="100%">${rows}</table></td></tr>`, locale);
}
