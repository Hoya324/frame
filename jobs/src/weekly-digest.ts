import { loadCatalog, daysUntil } from "./lib/catalog";
import { makeAdminClient, subscribersOf } from "./lib/supabaseAdmin";
import { loadSentRefs, recordSent } from "./lib/emailLog";
import { makeResendMailer, type Mailer } from "./lib/resendClient";
import { renderDigest, emailStrings } from "./lib/render";
import { env } from "./lib/env";

function isoWeek(d: Date): string {
  const date = new Date(Date.UTC(d.getFullYear(), d.getMonth(), d.getDate()));
  const day = date.getUTCDay() || 7;
  date.setUTCDate(date.getUTCDate() + 4 - day);
  const yearStart = new Date(Date.UTC(date.getUTCFullYear(), 0, 1));
  const week = Math.ceil(((date.getTime() - yearStart.getTime()) / 86400000 + 1) / 7);
  return `${date.getUTCFullYear()}-W${String(week).padStart(2, "0")}`;
}

export async function runWeeklyDigest(deps?: { mailer?: Mailer; today?: Date }): Promise<number> {
  const today = deps?.today ?? new Date();
  const mailer = deps?.mailer ?? makeResendMailer();
  const client = makeAdminClient();
  const ref = isoWeek(today);

  const catalog = loadCatalog();
  const featured = catalog.exhibitions
    .filter((e) => e.status === "ongoing" || e.status === "upcoming")
    .sort((a, b) => {
      const da = daysUntil(a.endDate, today) ?? 9999;
      const db = daysUntil(b.endDate, today) ?? 9999;
      return da - db;
    })
    .slice(0, 12);
  if (featured.length === 0) return 0;

  let sent = 0;
  for (const sub of await subscribersOf(client, "weekly_digest")) {
    const already = await loadSentRefs(client, sub.userId, "weekly_digest");
    if (already.has(ref)) continue;
    await mailer.send(sub.email, emailStrings(sub.locale).digestSubject, renderDigest(featured, env.siteUrl(), sub.locale));
    await recordSent(client, sub.userId, "weekly_digest", [ref]);
    sent++;
  }
  console.log(`weekly-digest: sent ${sent}`);
  return sent;
}

// Run when invoked directly.
if (import.meta.url === `file://${process.argv[1]}`) {
  runWeeklyDigest().catch((e) => { console.error(e); process.exit(1); });
}
