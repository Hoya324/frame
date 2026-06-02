import { loadCatalog } from "./lib/catalog";
import { makeAdminClient, subscribersOf } from "./lib/supabaseAdmin";
import { loadSentRefs, recordSent } from "./lib/emailLog";
import { makeResendMailer, type Mailer } from "./lib/resendClient";
import { matchCustom, type CustomFilters } from "./lib/match";
import { renderCustom, emailStrings } from "./lib/render";
import { env } from "./lib/env";

export async function runCustomAlerts(deps?: { mailer?: Mailer }): Promise<number> {
  const mailer = deps?.mailer ?? makeResendMailer();
  const client = makeAdminClient();
  const catalog = loadCatalog();

  let sent = 0;
  for (const sub of await subscribersOf(client, "custom")) {
    const matched = matchCustom(catalog.exhibitions, sub.filters as CustomFilters);
    if (matched.length === 0) continue;

    const already = await loadSentRefs(client, sub.userId, "custom");
    const fresh = matched.filter((e) => !already.has(e.id));
    if (fresh.length === 0) continue;

    await mailer.send(sub.email, emailStrings(sub.locale).customSubject, renderCustom(fresh.slice(0, 12), env.siteUrl(), sub.locale));
    await recordSent(client, sub.userId, "custom", fresh.map((e) => e.id));
    sent++;
  }
  console.log(`custom-alerts: sent ${sent}`);
  return sent;
}

if (import.meta.url === `file://${process.argv[1]}`) {
  runCustomAlerts().catch((e) => { console.error(e); process.exit(1); });
}
