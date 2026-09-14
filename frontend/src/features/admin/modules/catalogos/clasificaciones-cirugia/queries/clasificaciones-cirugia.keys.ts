import type { ClasificacionCirugiaListParams } from "@api/types";
import { createCatalogKeys } from "@features/admin/modules/catalogos/shared/queries/createCatalogKeys";

export const clasificacionCirugiaKeys = createCatalogKeys<ClasificacionCirugiaListParams>([
  "admin",
  "catalogos",
  "clasificaciones-cirugia",
]);
