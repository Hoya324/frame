import { describe, expect, it, vi } from "vitest";
import { getSubscriptions, upsertSubscription, type SubType } from "@/lib/subscriptions";

/* eslint-disable @typescript-eslint/no-explicit-any */
function fakeClient(rows: any[] = []) {
  const eqSel = vi.fn().mockResolvedValue({ data: rows, error: null });
  const select = vi.fn(() => ({ eq: eqSel }));
  const upsert = vi.fn().mockResolvedValue({ error: null });
  const from = vi.fn(() => ({ select, upsert }));
  return { client: { from } as any, from, select, eqSel, upsert };
}

describe("subscriptions data layer", () => {
  it("getSubscriptions returns rows keyed by type", async () => {
    const f = fakeClient([
      { user_id: "u1", type: "weekly_digest", enabled: true, filters: {} },
      { user_id: "u1", type: "custom", enabled: false, filters: { regions: ["서울"] } },
    ]);
    const map = await getSubscriptions(f.client, "u1");
    expect(f.from).toHaveBeenCalledWith("subscriptions");
    expect(f.eqSel).toHaveBeenCalledWith("user_id", "u1");
    expect(map.weekly_digest?.enabled).toBe(true);
    expect(map.custom?.filters.regions).toEqual(["서울"]);
  });

  it("upsertSubscription writes a full row", async () => {
    const f = fakeClient();
    const type: SubType = "closing_soon";
    await upsertSubscription(f.client, "u1", type, true, {});
    expect(f.upsert).toHaveBeenCalledWith(
      { user_id: "u1", type: "closing_soon", enabled: true, filters: {} },
      { onConflict: "user_id,type" },
    );
  });
});
