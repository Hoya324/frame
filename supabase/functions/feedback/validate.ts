const TYPES = ["bug", "feature", "other"];
const MAX_MESSAGE = 2000;
const MAX_IMAGES = 3;
const MAX_IMAGE_BYTES = 5 * 1024 * 1024;
const ALLOWED_IMAGE_TYPES = ["image/jpeg", "image/png", "image/webp"];
const EMAIL_RE = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;

export function base64Bytes(b64: string): number {
  const padding = b64.endsWith("==") ? 2 : b64.endsWith("=") ? 1 : 0;
  return Math.floor((b64.length * 3) / 4) - padding;
}

// deno-lint-ignore no-explicit-any
export function validate(body: any): string | null {
  if (!body || typeof body !== "object") return "invalid body";
  if (!TYPES.includes(body.type)) return "invalid type";
  if (typeof body.message !== "string") return "invalid message";
  const message = body.message.trim();
  if (message.length < 1 || message.length > MAX_MESSAGE) return "invalid message";
  if (typeof body.replyTo !== "string" || !EMAIL_RE.test(body.replyTo.trim())) return "invalid email";
  const images = body.images ?? [];
  if (!Array.isArray(images) || images.length > MAX_IMAGES) return "too many images";
  for (const img of images) {
    if (!img || typeof img.filename !== "string" || typeof img.dataBase64 !== "string") return "invalid image";
    if (!ALLOWED_IMAGE_TYPES.includes(img.type)) return "invalid image type";
    if (base64Bytes(img.dataBase64) > MAX_IMAGE_BYTES) return "image too large";
  }
  return null;
}
