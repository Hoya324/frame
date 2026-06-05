import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { PosterImage } from "@/components/PosterImage";

describe("PosterImage", () => {
  it("renders the poster <img> with referrerPolicy=no-referrer", () => {
    // Naver's blogthumb.pstatic.net (used by the gallery_now / ryugaheon
    // sources) returns 403 when the browser sends a non-Naver Referer. The
    // static export renders a plain <img>, so we must suppress the referrer or
    // every Naver-hosted poster breaks.
    render(
      <PosterImage
        src="https://blogthumb.pstatic.net/x/poster.jpg?type=s3"
        alt="국대호 개인전"
      />,
    );
    const img = screen.getByAltText("국대호 개인전");
    expect(img.tagName).toBe("IMG");
    expect(img).toHaveAttribute("referrerpolicy", "no-referrer");
  });

  it("shows the placeholder when there is no src", () => {
    render(<PosterImage src={null} alt="국대호 개인전" />);
    expect(
      screen.getByLabelText("국대호 개인전 (포스터 없음)"),
    ).toBeInTheDocument();
  });
});
