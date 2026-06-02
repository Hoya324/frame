import { describe, expect, it } from "vitest";
import { sourceLabel } from "@/lib/sources";

describe("sourceLabel", () => {
  it("maps a stored source id to its friendly label", () => {
    expect(sourceLabel("tokyo_art_beat", null)).toBe("Tokyo Art Beat");
    expect(sourceLabel("pgi", null)).toBe("PGI");
  });

  it("falls back to the URL host when source id is absent", () => {
    expect(sourceLabel(null, "https://www.tokyoartbeat.com/events/-/x")).toBe("Tokyo Art Beat");
    expect(sourceLabel(null, "https://blog.naver.com/noongamgo/123")).toBe("류가헌");
  });

  it("prefers the stored source id over the host", () => {
    // A naver-hosted ryugaheon post whose source id is explicit.
    expect(sourceLabel("ryugaheon", "https://blog.naver.com/x")).toBe("류가헌");
  });

  it("uses a bare hostname for an unknown source", () => {
    expect(sourceLabel(null, "https://unknown-gallery.example/show")).toBe("unknown-gallery.example");
  });

  it("returns null when nothing is available", () => {
    expect(sourceLabel(null, null)).toBeNull();
  });
});
