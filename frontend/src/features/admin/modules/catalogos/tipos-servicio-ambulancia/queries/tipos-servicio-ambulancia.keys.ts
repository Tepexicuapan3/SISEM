import type { TipoServicioAmbulanciaListParams } from "@api/types";
import { createCatalogKeys } from "@features/admin/modules/catalogos/shared/queries/createCatalogKeys";

export const tipoServicioAmbulanciaKeys = createCatalogKeys<TipoServicioAmbulanciaListParams>([
  "admin",
  "catalogos",
  "tipos-servicio-ambulancia",
]);
