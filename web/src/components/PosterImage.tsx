import Image from "next/image";

export function PosterImage({ src, alt }: { src: string | null; alt: string }) {
  if (!src) {
    return <div className="h-full w-full bg-panel2" aria-label={`${alt} (포스터 없음)`} />;
  }
  return (
    <Image src={src} alt={alt} fill sizes="(max-width:760px) 50vw, 280px"
      className="object-cover" unoptimized />
  );
}
