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
Deno.test("rejects null body", () => assertEq(validate(null), "invalid body", "null"));
Deno.test("rejects oversized image", () => {
  const big = "A".repeat(Math.ceil((5 * 1024 * 1024 + 1) / 3) * 4);
  const img = { filename: "big.png", type: "image/png", dataBase64: big };
  assertEq(validate({ type: "bug", message: "hi", replyTo: "a@b.co", images: [img] }), "image too large", "big");
});
