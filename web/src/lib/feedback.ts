import type { SupabaseClient } from "@supabase/supabase-js";

export const FEEDBACK_TYPES = ["bug", "feature", "other"] as const;
export type FeedbackType = (typeof FEEDBACK_TYPES)[number];

export const MAX_MESSAGE_LEN = 2000;
export const MAX_IMAGES = 3;
export const MAX_IMAGE_BYTES = 5 * 1024 * 1024;
export const ALLOWED_IMAGE_TYPES = ["image/jpeg", "image/png", "image/webp"];

export interface FeedbackImage { filename: string; type: string; dataBase64: string; }
export interface FeedbackInput {
  type: FeedbackType | null;
  message: string;
  replyTo: string;
  images: FeedbackImage[];
}

const EMAIL_RE = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;

export function base64Bytes(b64: string): number {
  const padding = b64.endsWith("==") ? 2 : b64.endsWith("=") ? 1 : 0;
  return Math.floor((b64.length * 3) / 4) - padding;
}

// Returns an i18n key for the first violation, or null when valid.
export function validateFeedbackInput(input: FeedbackInput): string | null {
  if (!input.type || !FEEDBACK_TYPES.includes(input.type)) return "feedback.errorType";
  const msg = input.message.trim();
  if (msg.length < 1 || msg.length > MAX_MESSAGE_LEN) return "feedback.errorMessage";
  if (!EMAIL_RE.test(input.replyTo.trim())) return "feedback.errorEmail";
  if (input.images.length > MAX_IMAGES) return "feedback.errorImageCount";
  for (const img of input.images) {
    if (!ALLOWED_IMAGE_TYPES.includes(img.type)) return "feedback.errorImageType";
    if (base64Bytes(img.dataBase64) > MAX_IMAGE_BYTES) return "feedback.errorImageSize";
  }
  return null;
}

export function fileToBase64(file: File): Promise<string> {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => {
      const result = typeof reader.result === "string" ? reader.result : "";
      resolve(result.split(",")[1] ?? "");
    };
    reader.onerror = () => reject(reader.error);
    reader.readAsDataURL(file);
  });
}

export async function submitFeedback(client: SupabaseClient, input: FeedbackInput): Promise<void> {
  const err = validateFeedbackInput(input);
  if (err) throw new Error(err);
  const { error } = await client.functions.invoke("feedback", {
    body: {
      type: input.type,
      message: input.message.trim(),
      replyTo: input.replyTo.trim(),
      images: input.images,
    },
  });
  if (error) throw error;
}
