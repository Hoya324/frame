import { loadCatalog, daysUntil } from "./lib/catalog";
import { makeAdminClient, subscribersOf, bookmarksOf } from "./lib/supabaseAdmin";
import { loadSentRefs, recordSent } from "./lib/emailLog";
import { makeResendMailer, type Mailer } from "./lib/resendClient";
import { renderClosingSoon } from "./lib/render";
import { env } from "./lib/env";

export async function runClosingSoon(deps?: { mailer?: Mailer; today?: Date }): Promise<number> {
  const today = deps?.today ?? new Date();
  const mailer = deps?.mailer ?? makeResendMailer();
  const client = makeAdminClient();
  const catalog = loadCatalog();
  const byId = new Map(catalog.exhibitions.map((e) => [e.id, e]));

  let sent = 0;
  for (const sub of await subscribersOf(client, "closing_soon")) {
    const ids = await bookmarksOf(client, sub.userId);
    const due: { e: typeof catalog.exhibitions[number]; dday: number }[] = [];
    for (const id of ids) {
      const e = byId.get(id);
      if (!e || e.status !== "ongoing") continue;
      const d = daysUntil(e.endDate, today);
      if (d === 3 || d === 1) due.push({ e, dday: d });
    }
    if (due.length === 0) continue;

    const already = await loadSentRefs(client, sub.userId, "closing_soon");
    const fresh = due.filter(({ e, dday }) => !already.has(`${e.id}:${dday}`));
    if (fresh.length === 0) continue;

    await mailer.send(sub.email, "곧 종료되는 스크랩 전시", renderClosingSoon(fresh, env.siteUrl()));
    await recordSent(client, sub.userId, "closing_soon", fresh.map(({ e, dday }) => `${e.id}:${dday}`));
    sent++;
  }
  console.log(`closing-soon: sent ${sent}`);
  return sent;
}

if (import.meta.url === `file://${process.argv[1]}`) {
  runClosingSoon().catch((e) => { console.error(e); process.exit(1); });
}
