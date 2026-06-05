"use client";
import Image from "next/image";
import { useState } from "react";
import { ImageOff } from "lucide-react";

export function PosterImage({ src, alt }: { src: string | null; alt: string }) {
  const [failedSrc, setFailedSrc] = useState<string | null>(null);
  const broken = src !== null && failedSrc === src;

  if (!src || broken) {
    return (
      <div
        className="flex h-full w-full items-center justify-center bg-panel2"
        aria-label={`${alt} (포스터 없음)`}
      >
        <ImageOff className="h-8 w-8 text-tx3" aria-hidden />
      </div>
    );
  }
  return (
    // referrerPolicy=no-referrer: Naver's blogthumb.pstatic.net (gallery_now /
    // ryugaheon posters) returns 403 when a non-Naver Referer is sent. The site
    // is a static export rendering a plain <img>, so without this every
    // Naver-hosted poster breaks (browser sends the frame-photo.cloud Referer).
    <Image src={src} alt={alt} fill sizes="(max-width:760px) 50vw, 280px"
      className="object-cover" unoptimized referrerPolicy="no-referrer"
      onError={() => setFailedSrc(src)} />
  );
}
