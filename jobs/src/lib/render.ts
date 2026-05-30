import type { JobExhibition } from "./catalog";

function esc(s: string): string {
  return s.replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]!));
}

function card(e: JobExhibition, siteUrl: string, badge?: string): string {
  const url = `${siteUrl}/exhibitions/${encodeURIComponent(e.id)}`;
  const sub = [e.venueName, e.region].filter(Boolean).map((s) => esc(s!)).join(" · ");
  return `
    <tr><td style="padding:12px 0;border-bottom:1px solid #222;">
      <a href="${url}" style="color:#fff;text-decoration:none;font-weight:700;font-size:16px;">
        ${badge ? `<span style="background:#fff;color:#000;border-radius:999px;padding:2px 8px;font-size:11px;margin-right:8px;">${esc(badge)}</span>` : ""}${esc(e.title)}
      </a>
      <div style="color:#9a9a9a;font-size:13px;margin-top:4px;">${sub}</div>
    </td></tr>`;
}

function shell(title: string, body: string): string {
  return `<!doctype html><html><body style="margin:0;background:#000;color:#fff;font-family:-apple-system,BlinkMacSystemFont,Helvetica,Arial,sans-serif;">
    <table width="100%" cellpadding="0" cellspacing="0" style="max-width:560px;margin:0 auto;padding:28px;">
      <tr><td style="font-weight:800;font-size:22px;letter-spacing:-0.03em;padding-bottom:8px;">FRAME</td></tr>
      <tr><td style="color:#9a9a9a;font-size:14px;padding-bottom:16px;">${esc(title)}</td></tr>
      ${body}
    </table></body></html>`;
}

export function renderDigest(items: JobExhibition[], siteUrl: string): string {
  const rows = items.map((e) => card(e, siteUrl)).join("");
  return shell("이번 주의 전시", `<tr><td><table width="100%">${rows}</table></td></tr>`);
}

export function renderClosingSoon(items: { e: JobExhibition; dday: number }[], siteUrl: string): string {
  const rows = items.map(({ e, dday }) => card(e, siteUrl, `D-${dday}`)).join("");
  return shell("스크랩한 전시가 곧 끝나요", `<tr><td><table width="100%">${rows}</table></td></tr>`);
}

export function renderCustom(items: JobExhibition[], siteUrl: string): string {
  const rows = items.map((e) => card(e, siteUrl, "NEW")).join("");
  return shell("관심 조건에 맞는 새 전시", `<tr><td><table width="100%">${rows}</table></td></tr>`);
}
