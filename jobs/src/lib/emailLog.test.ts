import { describe, expect, it, vi } from "vitest";
import { loadSentRefs, recordSent } from "./emailLog";

/* eslint-disable @typescript-eslint/no-explicit-any */
function fakeClient(rows: { ref: string }[] = []) {
  const eq2 = vi.fn().mockResolvedValue({ data: rows, error: null });
  const eq1 = vi.fn(() => ({ eq: eq2 }));
  const select = vi.fn(() => ({ eq: eq1 }));
  const insert = vi.fn().mockResolvedValue({ error: null });
  const from = vi.fn(() => ({ select, insert }));
  return { client: { from } as any, from, select, eq1, eq2, insert };
}

describe("emailLog", () => {
  it("loadSentRefs returns a Set of refs for (user, type)", async () => {
    const f = fakeClient([{ ref: "r1" }, { ref: "r2" }]);
    const refs = await loadSentRefs(f.client, "u1", "closing_soon");
    expect(f.from).toHaveBeenCalledWith("email_log");
    expect(f.eq1).toHaveBeenCalledWith("user_id", "u1");
    expect(f.eq2).toHaveBeenCalledWith("type", "closing_soon");
    expect(refs).toEqual(new Set(["r1", "r2"]));
  });

  it("recordSent inserts one row per ref", async () => {
    const f = fakeClient();
    await recordSent(f.client, "u1", "custom", ["a", "b"]);
    expect(f.insert).toHaveBeenCalledWith([
      { user_id: "u1", type: "custom", ref: "a" },
      { user_id: "u1", type: "custom", ref: "b" },
    ]);
  });

  it("recordSent with no refs does nothing", async () => {
    const f = fakeClient();
    await recordSent(f.client, "u1", "custom", []);
    expect(f.insert).not.toHaveBeenCalled();
  });
});
