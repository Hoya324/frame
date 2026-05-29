import data from "../../public/data/exhibitions.json";
import { parseCatalog, type Catalog } from "@/lib/catalog";

let cached: Catalog | null = null;
export function loadCatalogSync(): Catalog {
  if (!cached) cached = parseCatalog(data);
  return cached;
}
