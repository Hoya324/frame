import { notFound } from "next/navigation";
import { loadCatalog } from "@/lib/catalog";
import { ExhibitionDetailView } from "@/components/ExhibitionDetailView";

export async function generateStaticParams() {
  const cat = await loadCatalog();
  return cat.exhibitions.map((e) => ({ id: e.id }));
}

export default async function ExhibitionDetail({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  const cat = await loadCatalog();
  const e = cat.exhibitions.find((x) => x.id === id);
  if (!e) notFound();

  return <ExhibitionDetailView e={e} />;
}
