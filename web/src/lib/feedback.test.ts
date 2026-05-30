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
  it("rejects oversized image", () => {
    const bigB64 = "A".repeat(Math.ceil((5 * 1024 * 1024 + 1) / 3) * 4);
    const img = { filename: "big.png", type: "image/png", dataBase64: bigB64 };
    expect(validateFeedbackInput({ ...valid, images: [img] })).toBe("feedback.errorImageSize");
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
