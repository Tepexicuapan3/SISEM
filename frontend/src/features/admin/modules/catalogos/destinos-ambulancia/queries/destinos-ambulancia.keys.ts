import type { DestinoAmbulanciaListParams } from "@api/types";
import { createCatalogKeys } from "@features/admin/modules/catalogos/shared/queries/createCatalogKeys";

export const destinoAmbulanciaKeys = createCatalogKeys<DestinoAmbulanciaListParams>([
  "admin",
  "catalogos",
  "destinos-ambulancia",
]);
