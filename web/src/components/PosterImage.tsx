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
    <Image src={src} alt={alt} fill sizes="(max-width:760px) 50vw, 280px"
      className="object-cover" unoptimized onError={() => setFailedSrc(src)} />
  );
}
