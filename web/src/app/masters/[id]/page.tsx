import { notFound } from "next/navigation";
import { loadMasters } from "@/lib/masters";
import { MasterDetailView } from "@/components/MasterDetailView";

export async function generateStaticParams() {
  const cat = await loadMasters();
  return cat.masters.map((m) => ({ id: m.id }));
}

export default async function MasterDetailPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  const cat = await loadMasters();
  const master = cat.masters.find((m) => m.id === id);
  if (!master) notFound();
  return <MasterDetailView master={master} />;
}
