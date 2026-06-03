"use client";
import { useState, type ChangeEvent } from "react";
import { useAuth } from "@/components/AuthProvider";
import { useLang } from "@/components/LanguageProvider";
import { getSupabase } from "@/lib/supabase";
import {
  submitFeedback, fileToBase64, validateFeedbackInput,
  FEEDBACK_TYPES, MAX_IMAGES, MAX_IMAGE_BYTES, ALLOWED_IMAGE_TYPES,
  type FeedbackType, type FeedbackImage,
} from "@/lib/feedback";
import { EVENTS, track } from "@/lib/analytics";

const TYPE_LABEL_KEY: Record<FeedbackType, string> = {
  bug: "feedback.typeBug",
  feature: "feedback.typeFeature",
  other: "feedback.typeOther",
};

export function FeedbackForm() {
  const { user } = useAuth();
  const { t } = useLang();
  const [type, setType] = useState<FeedbackType | null>(null);
  const [message, setMessage] = useState("");
  const [replyTo, setReplyTo] = useState(user?.email ?? "");
  const [images, setImages] = useState<FeedbackImage[]>([]);
  const [status, setStatus] = useState<"idle" | "sending" | "sent" | "error">("idle");
  const [errorKey, setErrorKey] = useState<string | null>(null);

  if (!user) return null;

  async function onPickFiles(e: ChangeEvent<HTMLInputElement>) {
    const files = Array.from(e.target.files ?? []);
    e.target.value = "";
    setErrorKey(null);
    const room = MAX_IMAGES - images.length;
    if (files.length > room) setErrorKey("feedback.errorImageCount");
    for (const f of files.slice(0, room)) {
      if (!ALLOWED_IMAGE_TYPES.includes(f.type)) { setErrorKey("feedback.errorImageType"); continue; }
      if (f.size > MAX_IMAGE_BYTES) { setErrorKey("feedback.errorImageSize"); continue; }
      const dataBase64 = await fileToBase64(f);
      setImages((prev) => (prev.length >= MAX_IMAGES ? prev : [...prev, { filename: f.name, type: f.type, dataBase64 }]));
    }
  }

  function removeImage(idx: number) {
    setImages((prev) => prev.filter((_, i) => i !== idx));
  }

  async function onSubmit() {
    setErrorKey(null);
    const invalid = validateFeedbackInput({ type, message, replyTo, images });
    if (invalid) { setStatus("error"); setErrorKey(invalid); return; }
    setStatus("sending");
    try {
      await submitFeedback(getSupabase(), { type, message, replyTo, images });
      track(EVENTS.feedbackSubmit, { type, has_images: images.length > 0 });
      setStatus("sent");
      setType(null); setMessage(""); setImages([]);
    } catch (e) {
      setStatus("error");
      const key = e instanceof Error ? e.message : "feedback.errorSend";
      setErrorKey(key.startsWith("feedback.") ? key : "feedback.errorSend");
    }
  }

  return (
    <div className="rounded-lg border border-line p-5">
      <div className="text-sm text-tx3">{t("feedback.title")}</div>
      <p className="mt-1 text-xs text-tx3">{t("feedback.desc")}</p>

      <div className="mt-4 text-xs text-tx3">{t("feedback.typeLabel")}</div>
      <div className="mt-2 flex flex-wrap gap-2">
        {FEEDBACK_TYPES.map((ty) => {
          const on = type === ty;
          return (
            <button key={ty} type="button" aria-pressed={on} onClick={() => { setType(ty); if (status === "sent") setStatus("idle"); }}
              className={`rounded-full px-3.5 py-1.5 text-[13px] font-medium transition ${
                on ? "border border-white bg-white font-semibold text-black"
                   : "border border-line text-tx2 hover:text-tx"}`}>
              {t(TYPE_LABEL_KEY[ty])}
            </button>
          );
        })}
      </div>

      <label htmlFor="fb-message" className="mt-4 block text-xs text-tx3">{t("feedback.messageLabel")}</label>
      <textarea id="fb-message" value={message} rows={4}
        onChange={(e) => { setMessage(e.target.value); if (status === "sent") setStatus("idle"); }}
        placeholder={t("feedback.messagePlaceholder")}
        className="mt-1 w-full resize-y rounded-md border border-line bg-panel2 px-3 py-2 text-sm outline-none focus:border-line2" />

      <label htmlFor="fb-email" className="mt-4 block text-xs text-tx3">{t("feedback.emailLabel")}</label>
      <input id="fb-email" type="email" value={replyTo}
        onChange={(e) => setReplyTo(e.target.value)}
        className="mt-1 w-full rounded-md border border-line bg-panel2 px-3 py-2 text-sm outline-none focus:border-line2" />

      <div className="mt-4 text-xs text-tx3">{t("feedback.photoLabel")}</div>
      <label className="mt-2 inline-block cursor-pointer rounded-md border border-line2 px-3 py-1.5 text-sm font-medium hover:bg-panel2">
        {t("feedback.photoAdd")}
        <input type="file" accept="image/jpeg,image/png,image/webp" multiple className="hidden" onChange={onPickFiles} />
      </label>
      {images.length > 0 && (
        <ul className="mt-2 space-y-1">
          {images.map((img, i) => (
            <li key={i} className="flex items-center justify-between rounded-md border border-line px-3 py-1.5 text-xs text-tx2">
              <span className="truncate">{img.filename}</span>
              <button type="button" onClick={() => removeImage(i)} className="ml-3 shrink-0 text-tx3 hover:text-tx">
                {t("feedback.remove")}
              </button>
            </li>
          ))}
        </ul>
      )}

      <button type="button" onClick={() => void onSubmit()} disabled={status === "sending"}
        className="mt-5 rounded-md bg-white px-5 py-2.5 text-sm font-semibold text-black disabled:opacity-50">
        {status === "sending" ? t("feedback.submitting") : t("feedback.submit")}
      </button>

      {status === "sent" && <p className="mt-3 text-sm text-tx2">{t("feedback.success")}</p>}
      {errorKey && <p className="mt-3 text-sm text-red-400">{t(errorKey)}</p>}
    </div>
  );
}
