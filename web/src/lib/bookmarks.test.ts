import { describe, expect, it, vi } from "vitest";
import { addBookmark, listBookmarkIds, removeBookmark } from "@/lib/bookmarks";

// Minimal fake matching the calls our data layer makes.
function fakeClient(rows: { exhibition_id: string }[] = []) {
  const eqSel = vi.fn().mockResolvedValue({ data: rows, error: null });
  const select = vi.fn(() => ({ eq: eqSel }));
  const insert = vi.fn().mockResolvedValue({ error: null });
  const eq2 = vi.fn().mockResolvedValue({ error: null });
  const eq1 = vi.fn(() => ({ eq: eq2 }));
  const del = vi.fn(() => ({ eq: eq1 }));
  const from = vi.fn(() => ({ select, insert, delete: del }));
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  return { client: { from } as any, from, select, eqSel, insert, del, eq1, eq2 };
}

describe("bookmarks data layer", () => {
  it("listBookmarkIds returns a Set of exhibition ids", async () => {
    const f = fakeClient([{ exhibition_id: "e1" }, { exhibition_id: "e2" }]);
    const ids = await listBookmarkIds(f.client, "u1");
    expect(f.from).toHaveBeenCalledWith("bookmarks");
    expect(f.eqSel).toHaveBeenCalledWith("user_id", "u1");
    expect(ids).toEqual(new Set(["e1", "e2"]));
  });

  it("addBookmark inserts user_id + exhibition_id", async () => {
    const f = fakeClient();
    await addBookmark(f.client, "u1", "e9");
    expect(f.insert).toHaveBeenCalledWith({ user_id: "u1", exhibition_id: "e9" });
  });

  it("removeBookmark deletes by user_id + exhibition_id", async () => {
    const f = fakeClient();
    await removeBookmark(f.client, "u1", "e9");
    expect(f.del).toHaveBeenCalled();
    expect(f.eq1).toHaveBeenCalledWith("user_id", "u1");
    expect(f.eq2).toHaveBeenCalledWith("exhibition_id", "e9");
  });
});
