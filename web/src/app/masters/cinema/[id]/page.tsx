import { notFound } from "next/navigation";
import { cinemaById, cinemaIds } from "@/lib/cinema";
import { CinemaDetailView } from "@/components/CinemaDetailView";

export function generateStaticParams() {
  return cinemaIds().map((id) => ({ id }));
}

export default async function CinemaDetailPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  const scene = cinemaById(id);
  if (!scene) notFound();
  return <CinemaDetailView scene={scene} />;
}
