import { validate } from "./validate.ts";

const DEFAULT_ORIGINS = "https://frame-photo.cloud,http://localhost:3000";
const ALLOWED_ORIGINS = (Deno.env.get("FEEDBACK_ALLOWED_ORIGINS") ?? DEFAULT_ORIGINS)
  .split(",").map((s) => s.trim()).filter(Boolean);

const TYPE_LABEL: Record<string, string> = { bug: "버그", feature: "기능 제안", other: "기타" };

function corsHeaders(origin: string | null): Record<string, string> {
  const allow = origin && ALLOWED_ORIGINS.includes(origin) ? origin : ALLOWED_ORIGINS[0];
  return {
    "Access-Control-Allow-Origin": allow,
    "Access-Control-Allow-Headers": "authorization, content-type",
    "Access-Control-Allow-Methods": "POST, OPTIONS",
    Vary: "Origin",
  };
}

function json(payload: unknown, status: number, cors: Record<string, string>): Response {
  return new Response(JSON.stringify(payload), {
    status,
    headers: { ...cors, "Content-Type": "application/json" },
  });
}

function escapeHtml(s: string): string {
  return s.replace(/[&<>"']/g, (c) =>
    ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c] as string));
}

function userIdFromJwt(auth: string | null): string {
  if (!auth) return "unknown";
  try {
    const seg = auth.replace("Bearer ", "").split(".")[1];
    const b64 = seg.replace(/-/g, "+").replace(/_/g, "/");
    const payload = JSON.parse(atob(b64));
    return payload.sub ?? "unknown";
  } catch {
    return "unknown";
  }
}

Deno.serve(async (req) => {
  const cors = corsHeaders(req.headers.get("origin"));
  if (req.method === "OPTIONS") return new Response("ok", { headers: cors });
  if (req.method !== "POST") return json({ error: "method not allowed" }, 405, cors);

  // Wrap the whole handler so that any unexpected throw still returns a
  // response carrying CORS headers. Without this, an uncaught exception makes
  // the Edge runtime emit a bare 500 with no CORS headers, which the browser
  // surfaces only as an opaque "CORS error" instead of a readable status.
  try {
    let body: unknown;
    try {
      body = await req.json();
    } catch {
      return json({ error: "invalid json" }, 400, cors);
    }

    const validationError = validate(body);
    if (validationError) return json({ error: validationError }, 400, cors);

    const apiKey = Deno.env.get("RESEND_API_KEY");
    const to = Deno.env.get("FEEDBACK_TO");
    const from = Deno.env.get("FEEDBACK_FROM");
    if (!apiKey || !to || !from) {
      console.error("feedback: missing RESEND_API_KEY / FEEDBACK_TO / FEEDBACK_FROM");
      return json({ error: "server misconfigured" }, 500, cors);
    }

    const b = body as { type: string; message: string; replyTo: string; images?: { filename: string; dataBase64: string }[] };
    const userId = userIdFromJwt(req.headers.get("authorization"));
    const typeLabel = TYPE_LABEL[b.type] ?? b.type;
    const subject = `[FRAME 제보][${typeLabel}] ${b.message.slice(0, 40)}`;
    const html = [
      "<h2>FRAME 제보</h2>",
      `<p><b>유형:</b> ${escapeHtml(typeLabel)}</p>`,
      `<p><b>제보자 이메일:</b> ${escapeHtml(b.replyTo)}</p>`,
      `<p><b>user_id:</b> ${escapeHtml(userId)}</p>`,
      "<hr/>",
      `<p style="white-space:pre-wrap">${escapeHtml(b.message)}</p>`,
    ].join("");
    const attachments = (b.images ?? []).map((img) => ({ filename: img.filename, content: img.dataBase64 }));

    let res: Response;
    try {
      res = await fetch("https://api.resend.com/emails", {
        method: "POST",
        headers: { Authorization: `Bearer ${apiKey}`, "Content-Type": "application/json" },
        body: JSON.stringify({ from, to, reply_to: b.replyTo, subject, html, attachments }),
      });
    } catch (err) {
      console.error("feedback: resend fetch threw", err);
      return json({ error: "email failed", detail: String(err) }, 502, cors);
    }

    if (!res.ok) {
      const detail = await res.text();
      console.error("feedback: resend failed", res.status, detail);
      return json({ error: "email failed", detail }, 502, cors);
    }
    return json({ ok: true }, 200, cors);
  } catch (err) {
    console.error("feedback: unhandled error", err);
    return json({ error: "internal", detail: String(err) }, 500, cors);
  }
});
