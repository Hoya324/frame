# 버그·피드백 제보 기능 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 마이페이지(로그인 전용)에서 유형·내용·답장 이메일과 선택 사진을 받아 Supabase Edge Function + Resend로 `hoyana1225@gmail.com` 에 메일을 보낸다.

**Architecture:** 정적 웹(GitHub Pages)은 Resend 키를 노출할 수 없으므로, 클라이언트는 로그인 JWT가 자동 첨부되는 `supabase.functions.invoke("feedback")`로 호출한다. Edge Function(Deno, verify_jwt 기본 활성)이 입력을 재검증하고 Resend REST API로 메일을 보내며, 사진은 base64로 받아 메일 첨부파일로 전달한다. DB 저장은 하지 않는다.

**Tech Stack:** Next.js 16(App Router, static export) · React 19 · Tailwind v4 · @supabase/supabase-js · Supabase Edge Functions(Deno) · Resend REST API · vitest + @testing-library/react · deno test.

> **주의:** `web/AGENTS.md`에 따르면 이 저장소의 Next.js는 학습 데이터와 다를 수 있다. 새 Next.js API를 쓰기 전 `web/node_modules/next/dist/docs/`를 확인할 것. 이 계획은 표준 client component(`"use client"`)와 기존 패턴만 사용한다.

---

## File Structure

신규/수정 파일과 책임:

- `web/src/lib/feedback.ts` (신규) — 클라이언트 검증 규칙·상수, `File`→base64 변환, `functions.invoke` 래퍼. 단일 진실 공급원(검증 상수).
- `web/src/lib/feedback.test.ts` (신규) — 위 lib의 vitest 단위 테스트.
- `web/src/components/FeedbackForm.tsx` (신규) — 마이페이지 카드 UI(유형/내용/이메일/사진/제출).
- `web/src/components/FeedbackForm.test.tsx` (신규) — 폼 동작 테스트.
- `web/src/lib/i18n.ts` (수정) — ko/en/ja 3개 dict에 `feedback.*` 키 추가.
- `web/src/app/me/page.tsx` (수정) — `SubscriptionSettings` 아래에 `FeedbackForm` 렌더.
- `supabase/functions/feedback/validate.ts` (신규) — 순수 서버측 검증 함수(Deno 의존성 없음).
- `supabase/functions/feedback/validate_test.ts` (신규) — `deno test`용 검증 테스트.
- `supabase/functions/feedback/index.ts` (신규) — HTTP 핸들러, CORS, JWT에서 user_id 추출, Resend 호출.
- `README.md` (수정) — Edge Function 배포·시크릿 설정 절차.

---

## Task 1: 클라이언트 피드백 lib (검증 + base64 + invoke 래퍼)

**Files:**
- Create: `web/src/lib/feedback.ts`
- Test: `web/src/lib/feedback.test.ts`

- [ ] **Step 1: 실패하는 테스트 작성**

Create `web/src/lib/feedback.test.ts`:

```ts
import { describe, expect, it, vi } from "vitest";
import {
  validateFeedbackInput, base64Bytes, submitFeedback,
  type FeedbackInput,
} from "@/lib/feedback";

const valid: FeedbackInput = {
  type: "bug",
  message: "버튼이 안 눌려요",
  replyTo: "user@example.com",
  images: [],
};

describe("validateFeedbackInput", () => {
  it("returns null for valid input", () => {
    expect(validateFeedbackInput(valid)).toBeNull();
  });
  it("rejects missing type", () => {
    expect(validateFeedbackInput({ ...valid, type: null })).toBe("feedback.errorType");
  });
  it("rejects empty message", () => {
    expect(validateFeedbackInput({ ...valid, message: "   " })).toBe("feedback.errorMessage");
  });
  it("rejects bad email", () => {
    expect(validateFeedbackInput({ ...valid, replyTo: "nope" })).toBe("feedback.errorEmail");
  });
  it("rejects too many images", () => {
    const img = { filename: "a.png", type: "image/png", dataBase64: "AAAA" };
    expect(validateFeedbackInput({ ...valid, images: [img, img, img, img] })).toBe("feedback.errorImageCount");
  });
  it("rejects disallowed image type", () => {
    const img = { filename: "a.gif", type: "image/gif", dataBase64: "AAAA" };
    expect(validateFeedbackInput({ ...valid, images: [img] })).toBe("feedback.errorImageType");
  });
});

describe("base64Bytes", () => {
  it("estimates decoded byte length", () => {
    expect(base64Bytes("AAAA")).toBe(3);
    expect(base64Bytes("AAA=")).toBe(2);
    expect(base64Bytes("AA==")).toBe(1);
  });
});

describe("submitFeedback", () => {
  it("invokes the feedback function with a trimmed body", async () => {
    const invoke = vi.fn().mockResolvedValue({ data: { ok: true }, error: null });
    const client = { functions: { invoke } } as never;
    await submitFeedback(client, { ...valid, message: "  hi  " });
    expect(invoke).toHaveBeenCalledWith("feedback", {
      body: { type: "bug", message: "hi", replyTo: "user@example.com", images: [] },
    });
  });
  it("throws the validation key before invoking when input is invalid", async () => {
    const invoke = vi.fn();
    const client = { functions: { invoke } } as never;
    await expect(submitFeedback(client, { ...valid, type: null })).rejects.toThrow("feedback.errorType");
    expect(invoke).not.toHaveBeenCalled();
  });
});
```

- [ ] **Step 2: 테스트 실패 확인**

Run: `cd web && npx vitest run src/lib/feedback.test.ts`
Expected: FAIL — `Cannot find module '@/lib/feedback'`.

- [ ] **Step 3: 최소 구현 작성**

Create `web/src/lib/feedback.ts`:

```ts
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
```

- [ ] **Step 4: 테스트 통과 확인**

Run: `cd web && npx vitest run src/lib/feedback.test.ts`
Expected: PASS (8 tests).

- [ ] **Step 5: 커밋**

```bash
git add web/src/lib/feedback.ts web/src/lib/feedback.test.ts
git commit -m "feat(web): add feedback submission lib (validation, base64, invoke)"
```

---

## Task 2: i18n 키 추가 (ko/en/ja)

**Files:**
- Modify: `web/src/lib/i18n.ts`

검증 키와 UI 라벨을 세 dict 모두에 추가한다. 누락 시 `translate`가 ko 또는 key 자체로 폴백하지만, 세 언어 모두 채운다.

- [ ] **Step 1: ko dict에 키 추가**

`web/src/lib/i18n.ts`의 `const ko: Dict = { ... }` 안, `"sub.medium": "지역"` 줄(약 63행) 바로 다음에 추가:

```ts
  "feedback.title": "버그·피드백 제보",
  "feedback.desc": "불편한 점이나 제안을 보내주세요.",
  "feedback.typeLabel": "유형",
  "feedback.typeBug": "버그",
  "feedback.typeFeature": "기능 제안",
  "feedback.typeOther": "기타",
  "feedback.messageLabel": "내용",
  "feedback.messagePlaceholder": "무엇이 문제였는지, 또는 어떤 기능을 원하시는지 적어주세요.",
  "feedback.emailLabel": "답장받을 이메일",
  "feedback.photoLabel": "사진 첨부 (선택, 최대 3장)",
  "feedback.photoAdd": "사진 추가",
  "feedback.remove": "제거",
  "feedback.submit": "보내기",
  "feedback.submitting": "보내는 중…",
  "feedback.success": "제보가 전송되었습니다. 감사합니다!",
  "feedback.errorSend": "전송에 실패했습니다. 잠시 후 다시 시도해주세요.",
  "feedback.errorType": "유형을 선택해주세요.",
  "feedback.errorMessage": "내용을 입력해주세요.",
  "feedback.errorEmail": "올바른 이메일을 입력해주세요.",
  "feedback.errorImageCount": "사진은 최대 3장까지 첨부할 수 있습니다.",
  "feedback.errorImageSize": "사진은 각 5MB 이하여야 합니다.",
  "feedback.errorImageType": "JPG, PNG, WebP 형식만 첨부할 수 있습니다.",
```

- [ ] **Step 2: en dict에 키 추가**

`const en: Dict = { ... }` 안, `"sub.medium": "Medium"` 줄(약 146행) 다음에 추가:

```ts
  "feedback.title": "Report a bug or feedback",
  "feedback.desc": "Tell us about issues or suggestions.",
  "feedback.typeLabel": "Type",
  "feedback.typeBug": "Bug",
  "feedback.typeFeature": "Feature",
  "feedback.typeOther": "Other",
  "feedback.messageLabel": "Message",
  "feedback.messagePlaceholder": "Describe the issue or the feature you'd like.",
  "feedback.emailLabel": "Reply-to email",
  "feedback.photoLabel": "Attach photos (optional, up to 3)",
  "feedback.photoAdd": "Add photos",
  "feedback.remove": "Remove",
  "feedback.submit": "Send",
  "feedback.submitting": "Sending…",
  "feedback.success": "Your feedback was sent. Thank you!",
  "feedback.errorSend": "Failed to send. Please try again later.",
  "feedback.errorType": "Please choose a type.",
  "feedback.errorMessage": "Please enter a message.",
  "feedback.errorEmail": "Please enter a valid email.",
  "feedback.errorImageCount": "You can attach up to 3 photos.",
  "feedback.errorImageSize": "Each photo must be 5MB or smaller.",
  "feedback.errorImageType": "Only JPG, PNG, and WebP are allowed.",
```

- [ ] **Step 3: ja dict에 키 추가**

`const ja: Dict = { ... }` 안, `"sub.medium": "メディア"` 줄(약 228행) 다음에 추가:

```ts
  "feedback.title": "バグ・フィードバック報告",
  "feedback.desc": "不具合や提案をお知らせください。",
  "feedback.typeLabel": "種類",
  "feedback.typeBug": "バグ",
  "feedback.typeFeature": "機能提案",
  "feedback.typeOther": "その他",
  "feedback.messageLabel": "内容",
  "feedback.messagePlaceholder": "問題の内容や希望する機能をご記入ください。",
  "feedback.emailLabel": "返信用メール",
  "feedback.photoLabel": "写真添付（任意・最大3枚）",
  "feedback.photoAdd": "写真を追加",
  "feedback.remove": "削除",
  "feedback.submit": "送信",
  "feedback.submitting": "送信中…",
  "feedback.success": "送信しました。ありがとうございます！",
  "feedback.errorSend": "送信に失敗しました。後でもう一度お試しください。",
  "feedback.errorType": "種類を選択してください。",
  "feedback.errorMessage": "内容を入力してください。",
  "feedback.errorEmail": "有効なメールを入力してください。",
  "feedback.errorImageCount": "写真は最大3枚まで添付できます。",
  "feedback.errorImageSize": "各写真は5MB以下にしてください。",
  "feedback.errorImageType": "JPG・PNG・WebP形式のみ添付できます。",
```

- [ ] **Step 4: 타입체크/빌드 확인**

Run: `cd web && npx tsc --noEmit`
Expected: 에러 없음 (Dict는 `Record<string, string>`이라 키 추가만으로 통과).

- [ ] **Step 5: 커밋**

```bash
git add web/src/lib/i18n.ts
git commit -m "feat(web): add feedback form i18n keys (ko/en/ja)"
```

---

## Task 3: FeedbackForm 컴포넌트

**Files:**
- Create: `web/src/components/FeedbackForm.tsx`
- Test: `web/src/components/FeedbackForm.test.tsx`

- [ ] **Step 1: 실패하는 테스트 작성**

Create `web/src/components/FeedbackForm.test.tsx`:

```tsx
import { fireEvent, screen, waitFor } from "@testing-library/react";
import { describe, expect, it, vi, beforeEach } from "vitest";
import { renderWithLang } from "@/test/lang";

const invoke = vi.fn();
vi.mock("@/components/AuthProvider", () => ({
  useAuth: () => ({ user: { id: "u1", email: "me@example.com" } }),
}));
vi.mock("@/lib/supabase", () => ({
  getSupabase: () => ({ functions: { invoke } }),
}));

import { FeedbackForm } from "@/components/FeedbackForm";

describe("FeedbackForm", () => {
  beforeEach(() => invoke.mockReset());

  it("prefills the reply-to email from the logged-in user", () => {
    renderWithLang(<FeedbackForm />);
    expect(screen.getByDisplayValue("me@example.com")).toBeInTheDocument();
  });

  it("blocks submit and shows an error when type is not chosen", () => {
    renderWithLang(<FeedbackForm />);
    fireEvent.change(screen.getByLabelText("내용"), { target: { value: "문제 있어요" } });
    fireEvent.click(screen.getByText("보내기"));
    expect(screen.getByText("유형을 선택해주세요.")).toBeInTheDocument();
    expect(invoke).not.toHaveBeenCalled();
  });

  it("submits a valid report and shows success", async () => {
    invoke.mockResolvedValue({ data: { ok: true }, error: null });
    renderWithLang(<FeedbackForm />);
    fireEvent.click(screen.getByText("버그"));
    fireEvent.change(screen.getByLabelText("내용"), { target: { value: "버튼이 안 눌려요" } });
    fireEvent.click(screen.getByText("보내기"));
    await waitFor(() => expect(invoke).toHaveBeenCalledWith("feedback", {
      body: { type: "bug", message: "버튼이 안 눌려요", replyTo: "me@example.com", images: [] },
    }));
    expect(await screen.findByText("제보가 전송되었습니다. 감사합니다!")).toBeInTheDocument();
  });

  it("shows a send error when the function fails", async () => {
    invoke.mockResolvedValue({ data: null, error: new Error("boom") });
    renderWithLang(<FeedbackForm />);
    fireEvent.click(screen.getByText("기타"));
    fireEvent.change(screen.getByLabelText("내용"), { target: { value: "테스트" } });
    fireEvent.click(screen.getByText("보내기"));
    expect(await screen.findByText("전송에 실패했습니다. 잠시 후 다시 시도해주세요.")).toBeInTheDocument();
  });
});
```

- [ ] **Step 2: 테스트 실패 확인**

Run: `cd web && npx vitest run src/components/FeedbackForm.test.tsx`
Expected: FAIL — `Cannot find module '@/components/FeedbackForm'`.

- [ ] **Step 3: 컴포넌트 구현**

Create `web/src/components/FeedbackForm.tsx`:

```tsx
"use client";
import { useState, type ChangeEvent } from "react";
import { useAuth } from "@/components/AuthProvider";
import { useLang } from "@/components/LanguageProvider";
import { getSupabase } from "@/lib/supabase";
import {
  submitFeedback, fileToBase64,
  FEEDBACK_TYPES, MAX_IMAGES, MAX_IMAGE_BYTES, ALLOWED_IMAGE_TYPES,
  type FeedbackType, type FeedbackImage,
} from "@/lib/feedback";

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
    for (const f of files) {
      if (images.length >= MAX_IMAGES) { setErrorKey("feedback.errorImageCount"); break; }
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
    setStatus("sending");
    try {
      await submitFeedback(getSupabase(), { type, message, replyTo, images });
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
            <button key={ty} type="button" onClick={() => setType(ty)}
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
        onChange={(e) => setMessage(e.target.value)}
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
```

- [ ] **Step 4: 테스트 통과 확인**

Run: `cd web && npx vitest run src/components/FeedbackForm.test.tsx`
Expected: PASS (4 tests).

- [ ] **Step 5: 커밋**

```bash
git add web/src/components/FeedbackForm.tsx web/src/components/FeedbackForm.test.tsx
git commit -m "feat(web): add FeedbackForm component"
```

---

## Task 4: 마이페이지에 폼 연결

**Files:**
- Modify: `web/src/app/me/page.tsx`

- [ ] **Step 1: import 추가**

`web/src/app/me/page.tsx` 상단 import 블록(3행 `SubscriptionSettings` import 다음)에 추가:

```tsx
import { FeedbackForm } from "@/components/FeedbackForm";
```

- [ ] **Step 2: 렌더 추가**

`<div className="mt-4"><SubscriptionSettings /></div>` 줄(약 38행) 바로 다음에 추가:

```tsx
      <div className="mt-4"><FeedbackForm /></div>
```

- [ ] **Step 3: 타입체크 + 전체 테스트**

Run: `cd web && npx tsc --noEmit && npx vitest run`
Expected: 타입 에러 없음, 모든 테스트 PASS.

- [ ] **Step 4: 커밋**

```bash
git add web/src/app/me/page.tsx
git commit -m "feat(web): show FeedbackForm on My Page"
```

---

## Task 5: Edge Function 검증 모듈 (순수 함수 + deno test)

**Files:**
- Create: `supabase/functions/feedback/validate.ts`
- Test: `supabase/functions/feedback/validate_test.ts`

> Edge Function은 Deno 런타임이므로 vitest가 아닌 `deno test`로 검증한다. deno 미설치 시 `brew install deno`.

- [ ] **Step 1: 실패하는 테스트 작성**

Create `supabase/functions/feedback/validate_test.ts`:

```ts
import { validate, base64Bytes } from "./validate.ts";

function assertEq(actual: unknown, expected: unknown, label: string) {
  if (actual !== expected) throw new Error(`${label}: expected ${expected}, got ${actual}`);
}

const valid = { type: "bug", message: "hi", replyTo: "a@b.co", images: [] };

Deno.test("accepts valid input", () => assertEq(validate(valid), null, "valid"));
Deno.test("rejects bad type", () => assertEq(validate({ ...valid, type: "x" }), "invalid type", "type"));
Deno.test("rejects empty message", () => assertEq(validate({ ...valid, message: "   " }), "invalid message", "msg"));
Deno.test("rejects bad email", () => assertEq(validate({ ...valid, replyTo: "nope" }), "invalid email", "email"));
Deno.test("rejects too many images", () => {
  const img = { filename: "a.png", type: "image/png", dataBase64: "AAAA" };
  assertEq(validate({ ...valid, images: [img, img, img, img] }), "too many images", "count");
});
Deno.test("rejects disallowed image type", () => {
  const img = { filename: "a.gif", type: "image/gif", dataBase64: "AAAA" };
  assertEq(validate({ ...valid, images: [img] }), "invalid image type", "imgtype");
});
Deno.test("base64Bytes estimates length", () => {
  assertEq(base64Bytes("AAAA"), 3, "b64-3");
  assertEq(base64Bytes("AA=="), 1, "b64-1");
});
```

- [ ] **Step 2: 테스트 실패 확인**

Run: `cd supabase/functions/feedback && deno test`
Expected: FAIL — `Module not found "./validate.ts"`.

- [ ] **Step 3: 검증 모듈 구현**

Create `supabase/functions/feedback/validate.ts`:

```ts
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
  if (typeof body.message !== "string" || body.message.trim().length < 1 || body.message.length > MAX_MESSAGE) {
    return "invalid message";
  }
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
```

- [ ] **Step 4: 테스트 통과 확인**

Run: `cd supabase/functions/feedback && deno test`
Expected: PASS (7 tests).

- [ ] **Step 5: 커밋**

```bash
git add supabase/functions/feedback/validate.ts supabase/functions/feedback/validate_test.ts
git commit -m "feat(edge): add feedback validation module"
```

---

## Task 6: Edge Function HTTP 핸들러 (CORS + Resend)

**Files:**
- Create: `supabase/functions/feedback/index.ts`

> 로컬 타입체크: `deno check index.ts`. 핸들러 자체의 단위 테스트는 외부 호출(fetch/env)에 의존하므로 작성하지 않고, Task 8의 수동 검증으로 확인한다. 순수 로직(검증)은 Task 5에서 테스트됨.

- [ ] **Step 1: 핸들러 구현**

Create `supabase/functions/feedback/index.ts`:

```ts
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
    const payload = JSON.parse(atob(auth.replace("Bearer ", "").split(".")[1]));
    return payload.sub ?? "unknown";
  } catch {
    return "unknown";
  }
}

Deno.serve(async (req) => {
  const cors = corsHeaders(req.headers.get("origin"));
  if (req.method === "OPTIONS") return new Response("ok", { headers: cors });
  if (req.method !== "POST") return json({ error: "method not allowed" }, 405, cors);

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

  // body is validated above.
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

  const res = await fetch("https://api.resend.com/emails", {
    method: "POST",
    headers: { Authorization: `Bearer ${apiKey}`, "Content-Type": "application/json" },
    body: JSON.stringify({ from, to, reply_to: b.replyTo, subject, html, attachments }),
  });

  if (!res.ok) {
    console.error("feedback: resend failed", res.status, await res.text());
    return json({ error: "email failed" }, 502, cors);
  }
  return json({ ok: true }, 200, cors);
});
```

- [ ] **Step 2: 타입체크**

Run: `cd supabase/functions/feedback && deno check index.ts`
Expected: 에러 없음.

- [ ] **Step 3: 커밋**

```bash
git add supabase/functions/feedback/index.ts
git commit -m "feat(edge): add feedback function (CORS, JWT user id, Resend send)"
```

---

## Task 7: 배포·시크릿 문서화

**Files:**
- Modify: `README.md`

- [ ] **Step 1: README에 섹션 추가**

`README.md` 끝에 추가:

```markdown
## 피드백 제보 (Supabase Edge Function)

마이페이지의 버그·피드백 폼은 `supabase/functions/feedback` Edge Function을 통해
Resend로 메일을 보낸다. 클라이언트는 로그인 JWT로만 호출할 수 있다(verify_jwt 기본 활성).

### 시크릿 설정 (한 번)

    supabase secrets set RESEND_API_KEY=re_xxx
    supabase secrets set FEEDBACK_TO=hoyana1225@gmail.com
    supabase secrets set FEEDBACK_FROM="FRAME <notify@frame-photo.cloud>"
    # 선택: 허용 오리진 (기본 https://frame-photo.cloud,http://localhost:3000)
    supabase secrets set FEEDBACK_ALLOWED_ORIGINS="https://frame-photo.cloud"

`FEEDBACK_FROM`의 도메인은 Resend에서 검증된 발신 도메인이어야 한다.

### 배포

    supabase functions deploy feedback

`functions deploy`는 기본적으로 JWT 검증을 켠 채 배포한다(`--no-verify-jwt` 금지).

### 로컬 테스트

    cd supabase/functions/feedback && deno test
```

- [ ] **Step 2: 커밋**

```bash
git add README.md
git commit -m "docs: document feedback Edge Function secrets and deploy"
```

---

## Task 8: 수동 검증 (전체 흐름)

**Files:** 없음 (수동 확인)

- [ ] **Step 1: 시크릿 설정 및 함수 배포**

Run:
```bash
supabase secrets set RESEND_API_KEY=re_xxx FEEDBACK_TO=hoyana1225@gmail.com FEEDBACK_FROM="FRAME <notify@frame-photo.cloud>"
supabase functions deploy feedback
```
Expected: 배포 성공 메시지.

- [ ] **Step 2: 웹 dev 서버에서 폼 동작 확인**

Run: `cd web && npm run dev`
브라우저에서 `/me` → Google 로그인 → "버그·피드백 제보" 카드 확인:
- 유형 미선택 제출 → "유형을 선택해주세요." 표시
- 유형 선택 + 내용 입력 + (선택) 사진 1장 첨부 → 보내기 → "제보가 전송되었습니다. 감사합니다!" 표시
Expected: 위 동작 모두 정상, 콘솔/네트워크에 401·CORS 에러 없음.

- [ ] **Step 3: 수신 메일 확인**

`hoyana1225@gmail.com` 받은편지함에서:
- 제목 `[FRAME 제보][버그] …`
- 본문에 유형·제보자 이메일·user_id·내용 포함
- 첨부한 사진이 첨부파일로 도착
- 메일에서 "답장" 시 수신자가 제보자가 입력한 이메일(reply-to)인지 확인
Expected: 모두 일치.

---

## Self-Review (작성자 점검 완료)

- **Spec coverage:** 로그인 전용(verify_jwt, useAuth 가드), 필수 3항목(유형/내용/이메일 검증), Supabase Edge Function + Resend(Task 5·6), 사진 첨부파일 전송(attachments), DB 미저장(테이블 없음), i18n 3언어(Task 2), 무료 티어 유지(GitHub Pages 그대로, Edge Function 무료). 모두 태스크로 커버됨.
- **Placeholder scan:** TBD/TODO 없음. 모든 코드 스텝에 실제 코드 포함.
- **Type consistency:** `FeedbackInput`/`FeedbackImage`/`FeedbackType` 명칭이 lib·컴포넌트에서 일치. Edge `validate`는 독립 모듈로 `body:any`를 받아 런타임 검증(웹 lib와 동일 규칙: 유형 3종, 2000자, 5MB, 3장, JPG/PNG/WebP). 클라이언트 검증 키(`feedback.error*`)는 i18n 키와 일치.
- **Note:** 웹 클라이언트 검증과 Edge 검증은 런타임이 달라 의도적으로 코드 중복(각 런타임의 신뢰 경계). 규칙 값은 양쪽 모두 동일하게 유지.
